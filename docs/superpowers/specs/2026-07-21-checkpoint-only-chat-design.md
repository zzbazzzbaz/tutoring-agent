# Checkpoint-Only Chat Architecture Design

> **Date**: 2026-07-21
> **Status**: Approved
> **Scope**: Backend + Frontend chat module - eliminate business message table, use LangGraph checkpoint as single source of truth

## Problem Statement

当前对话数据存了两份：LangGraph checkpoint（msgpack 二进制）+ `chat_event` 表（JSONB）。重复存储导致大量 sync bug：去重丢消息、tool_input 为 null、重复 quiz、时间戳错位。每次修一个 bug 又引入新的。

## Design Decision

**删除 `chat_event` 表，checkpoint 作为对话数据的唯一真相源。**

- 消息（user/agent/tool）：checkpoint 自动存储，不再手动写业务表
- quiz 数据：从 checkpoint 的 AIMessage.tool_calls 提取
- quiz 状态：从 `state.next`（interrupt 激活）+ ToolMessage（已答）推断
- `present_question` 工具：**完全不碰 DB**，只调 `interrupt()`
- `present_question` 工具：**删除 `answer` 和 `analysis` 参数**（冗余，agent 自行评估）
- 题目聚合分析表：本期不做，未来用定时任务从 checkpoint 聚合

## Architecture

### 保留的业务表

| 表 | 用途 |
|---|------|
| `user` | 账号、密码、角色 |
| `auth_token` | 登录 token |
| `session` | 会话元数据（mode, project_id, title, deleted_at, last_active_at） |
| `project` | 项目背景 Markdown、发布状态 |

### 删除的表

- `chat_event` - 所有数据在 checkpoint 中

### 写路径

#### `send_message` endpoint

```
1. 检查 is_interrupted（读 checkpoint state.next）
2. 检查 get_running_task（内存 task registry）
3. touch_session（更新 last_active_at）
4. 创建 background task: run_agent_background()
5. SSE 消费 queue
```

不存 user 消息到业务表 - `astream_events({"messages": [HumanMessage(...)]})` 自动写入 checkpoint。

#### `run_agent_background`（后台任务）

```python
async def run_agent_background(agent, session_id, user_msg, context, queue, ...):
    config = _stream_config(session_id)
    stream = await agent.astream_events(
        {"messages": [HumanMessage(content=user_msg)]},
        config=config, version="v3", context=context,
    )
    async for message in stream.messages:
        # 检测 tool_calls -> 发 tool_start 事件
        # 流式 text -> 发 text 事件
        # 不累积，不保存

    if await stream.interrupted():
        interrupts = await stream.interrupts()
        for it in interrupts:
            await queue.put({"event": "quiz_interrupt", "data": it.value})

    await queue.put({"event": "done", "data": {}})
```

**不调 `_save_results`**。不调 `_process_stream`。checkpoint 自动存一切。

#### `present_question` 工具

```python
async def present_question(topic, q_type, stem, options, config):
    from langgraph.types import interrupt
    quiz_id = str(uuid.uuid4())
    student_answer = interrupt({
        "question_id": quiz_id,
        "topic": topic, "q_type": q_type,
        "stem": stem, "options": options,
    })
    if student_answer.get("action") == "skip":
        return {"question_id": quiz_id, "action": "skipped"}
    return {"question_id": quiz_id, "student_answer": student_answer.get("answer", "")}
```

- 不碰 DB
- 不需要 answer/analysis 参数
- interrupt value 包含 quiz 展示数据（topic, q_type, stem, options）
- return value 进入 checkpoint 成为 ToolMessage

#### `resume_quiz` endpoint

同 `send_message`，启动 `run_resume_background` 后台任务。不存 DB。

### 读路径

#### `GET /sessions/{id}/history`

```python
async def build_history(agent, session_id):
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    messages = state.values.get("messages", [])

    items = _extract_items(messages)

    pending_quiz = None
    if state.next:
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    pending_quiz = intr.value
                    break

    processing = bool(get_running_task(session_id) and not get_running_task(session_id).done())

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}
```

#### `_extract_items` - 从 LangChain 消息转前端格式

```python
def _extract_items(messages) -> list[dict]:
    items = []
    pending_quiz_calls = []  # 待配对的 present_question 调用

    for msg in messages:
        if isinstance(msg, HumanMessage):
            items.append({"type": "user", "content": msg.text})

        elif isinstance(msg, AIMessage):
            # 提取 tool_calls
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("name", "")
                    args = tc.get("args", {})
                    if name == "present_question":
                        items.append({
                            "type": "quiz",
                            "quiz_id": "",  # 从后续 ToolMessage 获取
                            "topic": args.get("topic", ""),
                            "q_type": args.get("q_type", ""),
                            "stem": args.get("stem", ""),
                            "options": args.get("options"),
                            "status": "pending",  # 默认 pending，配对到 ToolMessage 后改为 answered
                            "user_answer": None,
                        })
                        pending_quiz_calls.append(len(items) - 1)
                    elif name:  # search_knowledge 等非 quiz 工具
                        items.append({
                            "type": "tool_call",
                            "tool_name": name,
                            "tool_input": args,
                        })
            # 提取文本
            if msg.text:
                items.append({"type": "agent", "content": msg.text})

        elif isinstance(msg, ToolMessage):
            # 配对到最近的 pending quiz
            content = msg.text or ""
            try:
                result = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                result = {}

            if pending_quiz_calls:
                idx = pending_quiz_calls.pop(0)
                if "action" in result and result["action"] == "skipped":
                    items[idx]["status"] = "skipped"
                elif "student_answer" in result:
                    items[idx]["status"] = "answered"
                    items[idx]["user_answer"] = result["student_answer"]
                items[idx]["quiz_id"] = result.get("question_id", "")

    return items
```

#### `is_interrupted` - 读 checkpoint

```python
async def is_interrupted(agent, session_id) -> bool:
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    return bool(state.next)
```

注意：`is_interrupted` 现在需要 `agent` 参数（读 checkpoint），不再是纯 DB 查询。

### History API Response

```json
{
  "items": [
    {"type": "user", "content": "你好"},
    {"type": "agent", "content": "你好！..."},
    {"type": "tool_call", "tool_name": "search_knowledge", "tool_input": {"query": "TCP三次握手"}},
    {"type": "quiz", "quiz_id": "...", "topic": "...", "q_type": "multi", "stem": "...", "options": ["A...", "B..."], "status": "answered", "user_answer": "B"},
    {"type": "agent", "content": "回答正确！..."}
  ],
  "pending_quiz": null,
  "processing": false
}
```

`pending_quiz` 格式（interrupt 激活时）：
```json
{
  "question_id": "...",
  "topic": "...",
  "q_type": "multi",
  "stem": "...",
  "options": ["A...", "B..."]
}
```

### SSE Protocol（不变）

```
event: text           {"content": "<token>"}
event: tool_start     {"tool_name": "search_knowledge", "tool_input": {"query": "..."}}
event: quiz_interrupt {question_id, topic, q_type, stem, options}
event: done           {}
event: error          {"message": "...", "code": "..."}
```

### 删除的代码

| 删除 | 原因 |
|------|------|
| `ChatEvent` model | 不再有业务消息表 |
| `chat_event` 表 | 数据在 checkpoint |
| `save_event`, `list_events`, `update_quiz_status`, `has_pending_quiz`, `get_last_user_event` | 不再需要 |
| `ToolEventData`, `QuizEventData` (repos 层) | 不再需要 |
| `_save_results` | 不再保存到 DB |
| `_process_stream` 累积逻辑 | 不再累积，只流式转发 |
| `sync_checkpoint_to_db`, `sync_tool_messages` | 已删除，不再需要 |
| `build_history` 中的 DB 查询 | 改为读 checkpoint |
| 前端 `ChatEvent` 类型 | 改为新的 item 类型 |

### `present_question` 参数变更

#### PresentQuestionArgs（删除 answer, analysis）

```python
class PresentQuestionArgs(BaseModel):
    topic: str = Field(description="知识点名称，如 TCP三次握手")
    q_type: Literal["single", "multi", "short"] = Field(description="题型：single=单选 multi=多选 short=简答")
    stem: str = Field(description="题干文本")
    options: list[str] | None = Field(
        None,
        description='选项列表数组，如 ["选项A","选项B","选项C","选项D"]。简答题传 null。'
    )
    # answer 和 analysis 删除
```

#### Prompt 更新

```
## 出题与评估流程
...
2. 在你的推理中设计题目：
   - 考察理解，不考死记硬背
   - 单选题 4 个选项；多选题 4-6 个选项；简答题无选项
3. 调用 present_question(topic, q_type, stem, options)
4. 工具会暂停等待学生答题，学生提交后返回 {question_id, student_answer}
5. 拿到学生答案后，基于你的专业知识自行评估对错
6. 在回复中给学生反馈，继续苏格拉底式追问

## 可用工具
- search_knowledge(query): 检索课程知识库（含知识图谱），返回相关知识片段
- present_question(topic, q_type, stem, options): 向学生展示一道题并等待作答，返回学生答案
```

### Frontend

#### Types

```typescript
interface HistoryItem {
  type: 'user' | 'agent' | 'tool_call' | 'quiz'
  // user/agent
  content?: string
  // tool_call
  tool_name?: string
  tool_input?: Record<string, unknown>
  // quiz
  quiz_id?: string
  topic?: string
  q_type?: 'single' | 'multi' | 'short'
  stem?: string
  options?: string[] | null
  status?: 'pending' | 'answered' | 'skipped'
  user_answer?: string | null
}

interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}

interface HistoryResponse {
  items: HistoryItem[]
  pending_quiz: QuizInterruptData | null
  processing: boolean
}
```

#### 前端渲染

```tsx
{items.map((item, idx) => {
  switch (item.type) {
    case 'user': return <MessageBubble key={idx} role="user" content={item.content} />
    case 'agent': return <MessageBubble key={idx} role="agent" content={item.content} />
    case 'tool_call': return <ToolCallBubble key={idx} toolName={item.tool_name} toolInput={item.tool_input} />
    case 'quiz': return <QuizCard key={idx} quiz={item} />
  }
})}
```

#### `selectSession`

```typescript
const history = await sessionsApi.getHistory(id)
set({
  items: history.items,
  pendingQuiz: history.pending_quiz,
  streamStatus: history.pending_quiz ? 'quiz_interrupted' : (history.processing ? 'streaming' : 'idle'),
})
```

#### `done` handler

不再需要创建 agent message item - 前端不存消息。SSE done 后直接设 `streamStatus = 'idle'`。刷新时从 History API 恢复完整数据。

#### `tool_start` handler

直接加一个 `{type: 'tool_call', ...}` 到 items，不需要 DB 相关字段。

## Error Handling

### Background task 失败

- `queue.put({event: error})` 通知前端
- 前端显示重试按钮
- 重试时重新发消息（checkpoint 会有重复的 HumanMessage，可接受）

### SSE 断开

- Background task 继续执行
- 前端 `recoverFromHistory` -> `GET /history` -> 读 checkpoint 恢复

### 刷新恢复

- `GET /history` 读 checkpoint -> 返回完整消息 + pending_quiz + processing
- 前端恢复到正确状态

## Testing

### 验证点

- History API 读 checkpoint，不查业务表
- `pending_quiz` 从 `state.tasks[].interrupts[].value` 取
- `is_interrupted` 从 `state.next` 判断
- quiz 状态正确推断（pending/answered/skipped）
- user_answer 从 ToolMessage 提取
- tool_call（search_knowledge）正确提取 tool_name + tool_input
- `present_question` 不碰 DB
- `present_question` 无 answer/analysis 参数
- 前端渲染 user/agent/tool_call/quiz 四种类型
- SSE 断开后刷新恢复正常
- 教师查看学生会话（通过 checkpoint）

### 不做（YAGNI）

- 题目聚合分析表（未来定时任务）
- checkpoint 清理策略
- retry 去重（可接受 checkpoint 中有重复消息）

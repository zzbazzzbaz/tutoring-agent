# Chat Module Unification & SSE Resilience Design

> **Date**: 2026-07-21
> **Status**: Approved
> **Scope**: Backend + Frontend chat module rewrite

## Problem Statement

当前对话模块存在以下问题：

1. **API 分散**：`GET /sessions/{id}/messages` 和 `GET /sessions/{id}/questions` 两个端点，前端手动 merge + sort。
2. **出题时 agent 文本丢失**：`stream_chat_events` 在 interrupt 时提前 return，不调用 `save_final_agent_message`，agent 出题前的引导文本未存 DB。前端 `done` handler 也在 quiz 时清空 `streamingContent` 不存消息。
3. **刷新不恢复 interrupt 状态**：`selectSession` 不检查 LangGraph checkpoint 的 interrupt 状态，刷新后 `streamStatus` 被重置为 `idle`，发消息触发 409 `SESSION_INTERRUPTED`。
4. **409 显示"网络错误"**：前端对 409 没有特殊处理，用户看到无关的错误提示。
5. **工具调用不可见**：`search_knowledge` 的查询语句对用户完全不可见。
6. **SSE 断线无恢复**：浏览器刷新、网络断开导致 SSE 中断后，agent 回复可能丢失（即使 LangGraph checkpoint 有完整结果）。
7. **scroll 不跟随 quiz**：`ChatView` 的 scroll effect 依赖 `[items, streamingContent]`，不包含 `pendingQuiz`，quiz 可能在视口外。

## Design Decisions

### Agent 断线恢复策略：两者结合

- **P0**：Checkpoint 恢复 — History API 从 LangGraph checkpoint 同步已完成的消息到 DB。SSE 断了 agent 就停，但已完成的结果可恢复。
- **P2**：后台任务 — Agent 在 `asyncio.create_task` 中跑，SSE 只 tails 输出。断了 agent 继续跑。前端轮询 History API 获取结果。

### 重试方式：自动恢复 + 手动重试

SSE 断开后等 2s 自动调 History API。如果 agent 已完成则无感知恢复；如果 agent 未完成则显示"重试"按钮。

### 旧 API：直接删除

删除 `GET /sessions/{id}/messages` 和 `GET /sessions/{id}/questions`，只保留 `GET /sessions/{id}/history`。前后端同时改，无兼容压力。

### 工具调用存储：方案 C

- `Message` 表新增 `role: "tool"`，存储非 quiz 工具调用（如 `search_knowledge`）的 `tool_name` + `tool_input` + `tool_output`。
- `present_question` 不存 Message 表，只存 Question 表。
- `Question` 表保持不变，管自己的状态流转（pending -> answered/skipped）。
- Message 表的 content 不可变；Question 表的字段可更新（status、user_answer 等）。
- 零冗余。

---

## Architecture

### Data Model

#### Message 表改动

```python
class Message(SQLModel, table=True):
    __tablename__ = "message"

    id: uuid.UUID (PK)
    session_id: uuid.UUID (FK -> session.id)
    role: str          # "user" | "agent" | "tool"   ← 新增 "tool"
    content: str       # user/agent: 文本; tool: 空字符串
    # 新增字段（仅 tool 角色使用）:
    tool_name: str | None       # "search_knowledge"
    tool_input: dict | None     # JSON: {"query": "网络安全隔离 DMZ"}
    tool_output: str | None     # 检索结果文本
    created_at: datetime
```

- `present_question` **不存此表**，只存 Question 表。
- `search_knowledge` 存此表，content 为空，`tool_name`/`tool_input`/`tool_output` 有值。
- content 不可变，tool 消息也不可变。

#### Question 表

不变。保持现有结构。

#### 不新增表

不需要 `tool_call` 表，直接复用 Message 表。

### Backend API

#### 删除

```
GET /sessions/{id}/messages     ← 删除
GET /sessions/{id}/questions    ← 删除
```

#### 新增

```
GET /sessions/{id}/history
```

**Response**:

```json
{
  "items": [
    {"type": "message", "id": "...", "role": "user", "content": "...", "created_at": "..."},
    {"type": "message", "id": "...", "role": "tool", "tool_name": "search_knowledge", "tool_input": {"query": "..."}, "created_at": "..."},
    {"type": "message", "id": "...", "role": "agent", "content": "...", "created_at": "..."},
    {"type": "quiz", "id": "...", "topic": "...", "stem": "...", "status": "answered", ...}
  ],
  "pending_quiz": null
}
```

**核心逻辑**：

1. 从 LangGraph checkpoint 读取 state，将 checkpoint 中有但 DB 没有的消息同步到 DB `message` 表：
   - AIMessage -> `role="agent"`, `content=msg.text`
   - ToolMessage -> `role="tool"`, `tool_name`/`tool_input`/`tool_output` 从对应 AIMessage 的 tool_calls 提取
   - 通过消息内容或 `tool_call_id` 去重，避免重复存储。
2. 检查 `state.next` 是否非空（=interrupt），如果是则读取 interrupt 数据作为 `pending_quiz`。
3. 重新查 DB 获取完整 messages + questions，按 `created_at` 排序合并为时间线。
4. 返回 `{items, pending_quiz}`。

#### POST /sessions/{id}/messages 增加重试支持

`SendMessageRequest` 新增 `retry: bool = False` 字段。

当 `retry=True` 时，后端检查最后一条 DB 消息是否是同内容的 user 消息，是则跳过存储（避免重复），直接重新启动 agent 流式响应。

#### POST /sessions/{id}/quiz/resume

不变。

### SSE Protocol

#### 现有事件（不变）

```
event: text           {"content": "<token>"}
event: quiz_interrupt {question_id, topic, q_type, stem, options}
event: done           {}
event: error          {"message": "...", "code": "..."}
```

#### 新增事件

```
event: tool_start     {"tool_name": "search_knowledge", "tool_input": {"query": "..."}}
```

- 在 `stream_chat_events` 中检测 AIMessage 的 `tool_calls` 字段。
- `present_question` 的 tool_start **不发**（已有 `quiz_interrupt` 处理）。
- 只发 `search_knowledge` 等非 quiz 工具。

#### `stream_chat_events` 改动

1. 在 `stream.messages` 迭代中，检测 AIMessage 的 `tool_calls`，对非 quiz 工具发射 `tool_start` 事件。
2. **修复**：interrupt 前调用 `save_final_agent_message` 保存 agent 文本。
3. **新增**：正常完成时调用 `save_tool_messages` 从 checkpoint 提取 ToolMessage 存到 DB。

#### `resume_quiz_events` 同理

同样的修复：interrupt 前保存文本 + tool 消息持久化。

#### SSE 心跳

每 15s 发 `b": heartbeat\n\n"`（SSE comment），防止代理超时断开。

#### `raw_stream` finally 块

即使客户端断开连接，`finally` 块也尝试从 checkpoint 保存 agent 文本和 tool 消息到 DB。即使保存失败，History API 的 checkpoint 同步兜底。

### Frontend

#### Types

- `MessageOut` 新增 `role: 'tool'` + `tool_name` + `tool_input` + `tool_output` 字段。
- 新增 `HistoryResponse` 类型 `{items: ChatItem[], pending_quiz: QuizInterruptData | null}`。
- `ChatItem` 的 streaming 类型移除，改用 store 的 `streamingContent`。

#### API Client

- 新增 `sessionsApi.getHistory(id)` 调用 `GET /sessions/{id}/history`。
- 删除 `listMessages`、`listQuestions`。

#### chat store — `selectSession`

一次调用 `getHistory` 拿到完整时间线 + interrupt 状态：
- 如果 `pending_quiz` 非空，设置 `streamStatus = 'quiz_interrupted'` + `pendingQuiz`。
- 否则 `streamStatus = 'idle'`。

#### chat store — `sendMessage` 的 `done` handler

- `streaming` 状态：保存 `streamingContent` 为 agent 消息，设 `idle`。
- `quiz_interrupted` 状态：**也保存** `streamingContent` 为 agent 消息（修复文本消失 bug），然后清空。
- `error` 状态：显示 toast，不移除 user 消息（消息已在 DB）。

#### chat store — `tool_start` handler

收到 `tool_start` 事件时，创建一个 `role: 'tool'` 的 ChatItem 加入 `items`。

#### chat store — SSE 断线自动恢复

`sendMessage` catch 块逻辑：
1. 不立即报错，等 2s。
2. 调用 `GET /history` 尝试恢复。
3. 如果 `pending_quiz` 非空 -> 恢复 quiz 状态。
4. 如果最后一条是 agent 消息 -> 恢复显示，`idle`。
5. 否则 -> 显示"重试"按钮，`error` + `RETRYABLE`。

#### chat store — 409 错误处理

检测 409 错误时：
1. 调用 `GET /history` 恢复 `pending_quiz`。
2. 设 `streamStatus = 'quiz_interrupted'`。
3. toast "请先回答上方题目"。
4. 不移除 user 消息。

#### chat store — `retryLastMessage` 方法

找到最后一条 user 消息，用 `retry=true` 重新调用 API。不重复存 user 消息。

#### 新增组件：ToolCallBubble

显示工具调用信息，例如：
```
🔍 搜索知识库: 网络安全隔离 DMZ...
```
居中显示，样式为 muted 小标签。不展示 tool_output。

#### ChatView.tsx 改动

- 渲染 `role: 'tool'` 的消息为 `ToolCallBubble`。
- scroll effect 依赖加 `pendingQuiz`。
- quiz_interrupted 时显示提示文字"请先回答上方题目"。
- error + RETRYABLE 时显示"重试"按钮。

#### ChatInput.tsx 改动

- `quiz_interrupted` 时 input disabled + 显示提示。
- `error` + `RETRYABLE` 时显示"重试"按钮。

---

## Error Handling & Resilience

### SSE 断线场景全覆盖

| 场景 | 后端行为 | 前端行为 |
|------|---------|---------|
| agent 已完成，done 未送达 | checkpoint 有结果；`raw_stream` finally 存 DB | catch -> 2s -> GET /history -> 发现 agent 消息 -> 恢复 |
| agent 正在生成 token | stream 被 cancel；checkpoint 有部分状态；finally 尝试存 | catch -> 2s -> GET /history -> 无 agent 消息 -> 显示"重试" |
| quiz_interrupt 已送达 | interrupt 在 checkpoint | catch -> 2s -> GET /history -> pending_quiz 恢复 |
| quiz_interrupt 未送达 | 同上 | 同上 |
| 对已中断 session 发消息 | 后端返回 409 | catch -> 检测 409 -> GET /history 恢复 quiz -> toast |
| 正常完成 | done 送达 | 正常处理 |

### 不做的事（YAGNI）

- **SSE Last-Event-ID 重连**：需要服务端事件缓冲，复杂度高。checkpoint 恢复已足够。
- **WebSocket**：当前不需要双向通信。
- **断线自动重连 SSE**：不重连同一个流，而是查 history 恢复。更简单更可靠。
- **P2 后台任务**：本期实现，见下方 P2 架构。

---

## Implementation Phases

### P0 — 核心修复 + 统一 API

- [ ] `Message` 模型新增 `tool_name`、`tool_input`、`tool_output` 字段
- [ ] `repos.py` 新增 `save_tool_message`、`get_last_message`
- [ ] `chat/service.py` 修复 `stream_chat_events`：interrupt 前调 `save_final_agent_message`
- [ ] `chat/service.py` 新增 `save_tool_messages`：从 checkpoint 提取 ToolMessage 存 DB
- [ ] `chat/service.py` 新增 `build_history`：合并 messages + questions + checkpoint 同步
- [ ] `chat/router.py` 新增 `GET /sessions/{id}/history`
- [ ] `chat/router.py` 删除 `GET /sessions/{id}/messages` 和 `GET /sessions/{id}/questions`
- [ ] `chat/schemas.py` 新增 `HistoryOut`、`ToolMessageOut`；`SendMessageRequest` 加 `retry`
- [ ] 前端 types 更新：`MessageOut` 加 tool 字段、新增 `HistoryResponse`
- [ ] 前端 `api/sessions.ts`：新增 `getHistory`，删除 `listMessages`/`listQuestions`
- [ ] 前端 `stores/chat.ts`：`selectSession` 改用 `getHistory`
- [ ] 前端 `stores/chat.ts`：`done` handler 在 quiz 时也保存文本
- [ ] 前端 `ChatView.tsx`：scroll 依赖加 `pendingQuiz`
- [ ] 前端 `stores/chat.ts`：`resume_quiz_events` 同样修复

### P1 — SSE 断线恢复

- [ ] `chat/service.py`：History API 从 checkpoint 同步逻辑
- [ ] `chat/service.py`：`raw_stream` finally 块调 `save_final_agent_message` + `save_tool_messages`
- [ ] `chat/sse.py`：SSE 心跳（15s）
- [ ] `chat/router.py`：`send_message` 支持 `retry=true`
- [ ] 前端 `stores/chat.ts`：SSE catch -> 2s -> `getHistory` 自动恢复
- [ ] 前端 `stores/chat.ts`：409 错误 -> `getHistory` 恢复 quiz
- [ ] 前端 `stores/chat.ts`：`retryLastMessage` 方法
- [ ] 前端 `ChatInput.tsx`：重试按钮 + quiz 提示

### P2 — 工具调用展示

- [ ] 后端 `stream_chat_events`：发射 `tool_start` SSE 事件
- [ ] 前端 `stores/chat.ts`：处理 `tool_start` 事件
- [ ] 前端 `ToolCallBubble.tsx` 组件
- [ ] 前端 `ChatView.tsx`：渲染 tool 消息

### P2（未来）— 后台任务

- Agent 在 `asyncio.create_task` 中执行，SSE tails 输出
- 断线后 agent 继续跑，前端轮询 history 获取结果

#### 架构

当前 P0/P1 中，agent 执行与 SSE 连接绑定：SSE 断开 -> agent 被 cancel。P2 将 agent 执行移到独立 `asyncio.Task`，SSE 只是消费方。

```
POST /messages
  ├─ save user message
  ├─ create asyncio.Task: run_agent(session_id, content)  <- 后台执行
  │    ├─ agent.astream_events()
  │    ├─ 逐事件写入 asyncio.Queue
  │    └─ 完成后 save_final_agent_message + save_tool_messages
  └─ SSE stream: consume from Queue  <- 断了无所谓，task 继续

GET /history
  ├─ 检查 task registry: session_id 是否有运行中的 task
  ├─ 如果有 -> 返回 processing: true
  └─ 如果无 -> 正常返回 history
```

#### Task Registry

```python
_running_tasks: dict[UUID, asyncio.Task] = {}

def get_running_task(session_id: UUID) -> asyncio.Task | None:
    task = _running_tasks.get(session_id)
    if task and not task.done():
        return task
    _running_tasks.pop(session_id, None)
    return None
```

- 同一 session 不允许并发 agent 任务。`POST /messages` 检查 registry，有运行中的 task 则返回 409 `SESSION_PROCESSING`。
- Agent 完成后从 registry 移除。
- 内存级，进程内有效。重启后丢失（checkpoint 恢复兜底）。

#### 后台执行函数

```python
async def run_agent_background(
    session_id, user_msg, context, queue, db_session_factory, agent,
):
    """在后台运行 agent，事件写入 queue。不依赖 SSE 连接。"""
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config, version="v3", context=context,
        )
        async for message in stream.messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if tc["name"] != "present_question":
                        await queue.put({"event": "tool_start", "data": {
                            "tool_name": tc["name"], "tool_input": tc["args"],
                        }})
            async for token in message.text:
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            await save_final_agent_message(agent, config, db_session, session_id)
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})
        else:
            await save_final_agent_message(agent, config, db_session, session_id)
            await save_tool_messages(agent, config, db_session, session_id)

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_agent_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

#### SSE 消费方

```python
async def raw_stream(queue: asyncio.Queue):
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield b": heartbeat\n\n"
                continue
            if event["event"] == "done":
                yield _sse(event["event"], event["data"]).encode()
                break
            yield _sse(event["event"], event["data"]).encode()
    finally:
        pass  # SSE 断开，但后台 task 继续
```

#### History API 增加 processing 状态

```python
async def get_history(session_id, agent, db):
    task = get_running_task(session_id)
    processing = bool(task and not task.done())
    # 仍然从 checkpoint 同步 + 返回 items + pending_quiz
    ...
    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}
```

#### 前端轮询

```typescript
async function recoverFromHistory(sessionId: string) {
  const { items, pending_quiz, processing } = await sessionsApi.getHistory(sessionId)
  if (pending_quiz) {
    set({ items, pendingQuiz: pending_quiz, streamStatus: 'quiz_interrupted' })
  } else if (processing) {
    set({ items, streamStatus: 'streaming' })
    setTimeout(() => recoverFromHistory(sessionId), 3000)
  } else {
    const lastAgentMsg = [...items].reverse().find(i => i.type === 'message' && i.data.role === 'agent')
    if (lastAgentMsg) {
      set({ items, streamStatus: 'idle' })
    } else {
      set({ items, streamStatus: 'error', lastError: { message: 'retry', code: 'RETRYABLE' } })
    }
  }
}
```

#### 实现清单

- [ ] 后端 `chat/service.py`：`run_agent_background` 函数
- [ ] 后端 `chat/service.py`：task registry（`_running_tasks` dict + `get_running_task`）
- [ ] 后端 `chat/sse.py`：`send_message` 改为创建后台 task + SSE 消费 queue
- [ ] 后端 `chat/sse.py`：`raw_stream` 从 queue 消费 + 心跳
- [ ] 后端 `chat/service.py`：`build_history` 增加 `processing` 字段
- [ ] 后端 `chat/sse.py`：`resume_quiz` 同样改为后台 task 模式
- [ ] 前端 `stores/chat.ts`：`recoverFromHistory` 支持 `processing` 轮询
- [ ] 前端 `types/session.ts`：`HistoryResponse` 增加 `processing: boolean`

---

## Testing

### 验证点

- 发消息后立即刷新 -> history 恢复 agent 回复
- 发消息后断网 -> 2s 后自动恢复或显示重试
- quiz 中断后刷新 -> quiz 状态恢复
- 对已中断 session 发消息 -> 409 -> 自动恢复 quiz
- 工具调用 -> ToolCallBubble 显示查询语句
- `present_question` 不出现在 `tool_start` 事件中
- 出题时 agent 引导文本不消失
- quiz 在视口内可见（scroll 跟随）
- `retry=true` 不重复存 user 消息
- SSE 心跳防止代理超时
- 后台任务：SSE 断开后 agent 继续执行，前端轮询 history 获取结果
- 后台任务：同一 session 并发请求被拒绝（409 SESSION_PROCESSING）
- 后台任务：History API 返回 `processing: true` 时前端自动轮询

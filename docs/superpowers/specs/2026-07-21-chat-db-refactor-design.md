# Chat Module Database Refactor Design

> **Date**: 2026-07-21
> **Status**: Approved
> **Scope**: Backend + Frontend chat module database refactor

## Problem Statement

当前对话模块有太多 bug，根因是**双数据源同步**：

1. **两个数据源**：DB `message` 表 + LangGraph checkpoint。History API 需要从 checkpoint 同步缺失消息到 DB，同步逻辑复杂且脆弱（去重、时间戳、tool_input 提取）。
2. **两张表**：`message` 表和 `question` 表，每次查 History 都要 merge + sort。
3. **同步 bug 频发**：相同内容去重丢消息、tool_input 为 null、tool 消息数量不对、时间戳错位。

## Design Decision

**彻底分离读写路径，单表存储，零 checkpoint 读取。**

- **写路径**（background task）：agent 跑完后一次性保存所有事件到 DB。`present_question` 工具在 interrupt 前把 quiz 存到 DB，resume 时更新 status。
- **读路径**（History API）：只查 DB，不碰 checkpoint。`pending_quiz` = `SELECT ... WHERE type='quiz' AND status='pending'`。
- **单表**：`chat_event` 替代 `message` + `question`，用 JSONB 存类型特定字段。

## Architecture

### Data Model

#### 新表：`chat_event`

```python
class ChatEvent(SQLModel, table=True):
    __tablename__ = "chat_event"

    id: uuid.UUID (PK, default uuid4)
    session_id: uuid.UUID (FK -> session.id, CASCADE, indexed)
    type: str            # "user" | "agent" | "tool" | "quiz"
    created_at: datetime (TIMESTAMPTZ, server_default now())

    # user/agent 消息
    content: str | None  # 文本内容; tool/quiz 时为 null

    # 类型特定数据（JSONB）
    data: dict | None    # tool: {tool_name, tool_input, tool_output}
                         # quiz: {topic, q_type, stem, options, answer, analysis, user_answer}

    # quiz 状态流转
    status: str | None   # quiz: pending/answered/skipped; 其他: null
    answered_at: datetime | None  # quiz 专用
```

各类型存储内容：

| type | content | data | status |
|------|---------|------|--------|
| user | "你好" | null | null |
| agent | "你好！..." | null | null |
| tool | null | `{"tool_name":"search_knowledge","tool_input":{"query":"..."},"tool_output":"..."}` | null |
| quiz | null | `{"topic":"...","q_type":"multi","stem":"...","options":[...],"answer":"A,B,C","analysis":"...","user_answer":"A,B"}` | pending -> answered/skipped |

#### 删除的表

- `message` 表 -> 数据迁移到 `chat_event`
- `question` 表 -> 数据迁移到 `chat_event`（type='quiz'）

#### 删除的字段

- `question.verdict` - 定义了但从未写入
- `question.diagnosis` - 定义了但从未写入

#### 保留不变的表

- `session`、`user`、`auth_token`、`project` - 不受影响

### 写路径

#### 发送消息（`send_message` endpoint）

```
1. INSERT chat_event (type='user', content=msg)
2. 创建 background task: run_agent_background()
3. SSE 消费 queue
```

#### `run_agent_background`（后台任务）

```
agent.astream_events()
  ├─ text token -> queue.put({event: text})
  ├─ tool_call -> queue.put({event: tool_start})
  └─ 完成/中断后:
       INSERT chat_event (type='agent', content=agent_text)
       INSERT chat_event (type='tool', data={tool_name, tool_input, tool_output})
         - 从 AIMessage.tool_calls 提取 tool_input
         - 跳过 present_question（quiz 有独立存储）
       queue.put({event: done})
  finally:
     _running_tasks.pop(session_id)
```

#### `present_question` 工具

```
1. INSERT chat_event (type='quiz', data={topic, q_type, stem, options, answer, analysis}, status='pending')
2. interrupt({question_id, topic, q_type, stem, options})
3. resume 后:
     UPDATE chat_event SET status='answered'/'skipped', data.user_answer=answer, answered_at=now()
     WHERE id = quiz_event_id
4. return {question_id, student_answer}
```

#### `resume_quiz` endpoint

```
1. 检查 pending quiz: SELECT ... WHERE type='quiz' AND status='pending'
2. 创建 background task: run_resume_background()
3. SSE 消费 queue
```

### 读路径

#### `GET /sessions/{id}/history`

```python
# 只查 DB，零 checkpoint 访问
events = await repos.list_events(db, session_id)  # SELECT * FROM chat_event ORDER BY created_at
pending = next((e for e in events if e.type == 'quiz' and e.status == 'pending'), None)
processing = bool(get_running_task(session_id))  # 内存查 task registry

return {
    "items": [event_to_dict(e) for e in events],
    "pending_quiz": event_to_dict(pending) if pending else None,
    "processing": processing,
}
```

#### `is_interrupted` 检查（写路径用）

```python
# 不再读 checkpoint，改读 DB
async def is_interrupted(db, session_id) -> bool:
    return await repos.has_pending_quiz(db, session_id)
    # SELECT EXISTS(SELECT 1 FROM chat_event WHERE type='quiz' AND status='pending' AND session_id=?)
```

### 删除的代码

| 函数 | 原因 |
|------|------|
| `sync_checkpoint_to_db` | 不再需要同步 |
| `sync_tool_messages` | 不再需要同步 |
| `save_final_agent_message` | 改为直接 INSERT，不需要从 checkpoint 读 |
| `save_tool_messages` | 改为直接 INSERT，在 background task 中提取 |
| `build_history` 中的 checkpoint 逻辑 | 改为纯 DB 查询 |
| `is_interrupted` 中的 checkpoint 逻辑 | 改为 DB 查询 |
| `repos.upsert_pending_question` | 改为 `repos.save_quiz_event` |
| `repos.update_question` | 改为 `repos.update_quiz_status` |
| `repos.list_messages` | 改为 `repos.list_events` |
| `repos.list_questions` | 合并到 `repos.list_events` |
| `repos.save_message` | 改为 `repos.save_event` |
| `repos.save_tool_message` | 合并到 `repos.save_event` |
| `repos.get_last_message` | 改为 `repos.get_last_user_event` |

### SSE 协议（不变）

```
event: text           {"content": "<token>"}
event: tool_start     {"tool_name": "search_knowledge", "tool_input": {"query": "..."}}
event: quiz_interrupt {question_id, topic, q_type, stem, options}
event: done           {}
event: error          {"message": "...", "code": "..."}
```

### 前端变更

#### Types

```typescript
interface ChatEvent {
  id: string
  session_id: string
  type: 'user' | 'agent' | 'tool' | 'quiz'
  created_at: string
  content: string | null
  data: {
    tool_name?: string
    tool_input?: Record<string, unknown>
    tool_output?: string
    topic?: string
    q_type?: 'single' | 'multi' | 'short'
    stem?: string
    options?: string[] | null
    answer?: string
    analysis?: string
    user_answer?: string | null
  } | null
  status: 'pending' | 'answered' | 'skipped' | null
  answered_at: string | null
}

interface HistoryResponse {
  items: ChatEvent[]
  pending_quiz: ChatEvent | null
  processing: boolean
}
```

`ChatItem` union type 删除，统一用 `ChatEvent`。

#### 前端渲染

```tsx
{items.map(event => {
  switch (event.type) {
    case 'user': return <MessageBubble message={event} />
    case 'agent': return <MessageBubble message={event} />
    case 'tool': return <ToolCallBubble message={event} />
    case 'quiz': return <QuizCard quiz={event} />
  }
})}
```

#### `selectSession` 逻辑

```typescript
const history = await sessionsApi.getHistory(id)
set({
  items: history.items,
  pendingQuiz: history.pending_quiz,
  streamStatus: history.pending_quiz ? 'quiz_interrupted' : (history.processing ? 'streaming' : 'idle'),
})
```

### 数据迁移

```sql
-- 1. 创建 chat_event 表
CREATE TABLE chat_event (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES session(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    content TEXT,
    data JSONB,
    status VARCHAR(20),
    answered_at TIMESTAMPTZ
);
CREATE INDEX idx_chat_event_session ON chat_event(session_id);
CREATE INDEX idx_chat_event_status ON chat_event(status) WHERE status IS NOT NULL;

-- 2. 迁移 message 表
INSERT INTO chat_event (id, session_id, type, created_at, content, data)
SELECT id, session_id, role, created_at, content,
  CASE WHEN role = 'tool' THEN jsonb_build_object(
    'tool_name', tool_name,
    'tool_input', tool_input,
    'tool_output', tool_output
  ) END
FROM message;

-- 3. 迁移 question 表
INSERT INTO chat_event (id, session_id, type, created_at, data, status, answered_at)
SELECT id, session_id, 'quiz', created_at,
  jsonb_build_object(
    'topic', topic,
    'q_type', q_type,
    'stem', stem,
    'options', options,
    'answer', answer,
    'analysis', analysis,
    'user_answer', user_answer
  ),
  status, answered_at
FROM question;

-- 4. 删除旧表
DROP TABLE message;
DROP TABLE question;
```

### LangGraph checkpoint 保留

LangGraph checkpoint 表（`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`）**保留不变**。它们用于：
- Agent 的对话上下文（消息历史）
- `interrupt()` / `Command(resume=...)` 机制
- `astream_events()` 的流式输出

我们的应用代码不再直接读 checkpoint，但 LangGraph 内部仍然使用它。

## Error Handling

### Background task 保存失败

如果 `run_agent_background` 在保存到 DB 时失败（DB 错误）：
- 消息丢失
- `queue.put({event: error})` 通知前端
- 前端显示"重试"按钮
- 重试时 agent 从 checkpoint 继续执行（checkpoint 有完整状态）

这是可接受的：DB 故障是罕见事件，且有重试机制兜底。

### SSE 断开

SSE 断开不影响 background task。Agent 继续跑，保存到 DB。前端通过 `recoverFromHistory` 轮询恢复。

## Testing

### 验证点

- History API 只查 DB，不碰 checkpoint
- `pending_quiz` 从 DB 查询（`type='quiz' AND status='pending'`）
- `is_interrupted` 从 DB 查询（不读 checkpoint）
- tool 消息有正确的 `tool_input`（从 AIMessage.tool_calls 提取）
- 相同内容的 agent 回复不会被去重跳过（单表无 sync 逻辑）
- quiz 答题后 status 正确更新为 answered/skipped
- 数据迁移后 chat_event 包含所有旧 message + question 数据
- 前端 ChatEvent 统一类型渲染正确
- 前端 pending_quiz 恢复正常

### 不验证（YAGNI）

- checkpoint 数据完整性（LangGraph 自己管）
- 多 session 并发（已有 task registry 防护）

# Chat Module Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the chat module's APIs, fix agent text loss on quiz interrupt, add SSE resilience with checkpoint recovery, display tool calls, and decouple agent execution from SSE via background tasks.

**Architecture:** Message table gains `role="tool"` for non-quiz tool calls. A unified `GET /sessions/{id}/history` endpoint replaces `/messages` + `/questions`, syncing from LangGraph checkpoint. SSE stream becomes a consumer of an `asyncio.Queue` fed by a background `asyncio.Task`, so disconnects don't cancel the agent. Frontend auto-recovers via History API polling.

**Tech Stack:** FastAPI, SQLModel, LangGraph 1.x, PostgreSQL (asyncpg), React 19, Zustand 5, Tailwind CSS v4

## Global Constraints

- DB columns use `TIMESTAMP(timezone=True)` + `server_default=func.now()`
- Python code uses `datetime.now(timezone.utc)` not `datetime.utcnow()`
- Bearer token auth (stateful AuthToken table), no JWT
- Tailwind v4 uses `@plugin` in CSS, not `tailwind.config.js` plugins
- `create_all` is idempotent but does NOT alter existing tables - manual ALTER TABLE needed
- No comments in code unless asked
- Frontend: `bun run typecheck && bun run build` for verification
- Backend: `uv run pytest` for integration tests (needs real DB + LightRAG + DashScope)

## File Structure

**Backend - modify:**
- `backend/src/tutoring/db/models.py` - Add tool fields to Message model
- `backend/src/tutoring/db/repos.py` - Add save_tool_message, get_last_message
- `backend/src/tutoring/chat/schemas.py` - Add HistoryOut, retry field
- `backend/src/tutoring/chat/service.py` - Fix bugs, add build_history, task registry, run_agent_background
- `backend/src/tutoring/chat/sse.py` - SSE consumer from queue, heartbeat, retry
- `backend/src/tutoring/chat/router.py` - History endpoint, delete old endpoints

**Frontend - modify:**
- `frontend/src/types/message.ts` - Add tool fields
- `frontend/src/types/session.ts` - Add HistoryResponse
- `frontend/src/types/chat.ts` - Update ChatItem
- `frontend/src/api/sessions.ts` - Add getHistory, remove old methods
- `frontend/src/api/chat.ts` - Add retry param
- `frontend/src/stores/chat.ts` - All store changes
- `frontend/src/features/chat/ChatView.tsx` - Scroll, tool render, hints
- `frontend/src/features/chat/ChatInput.tsx` - Retry button, quiz hint

**Frontend - create:**
- `frontend/src/features/chat/ToolCallBubble.tsx` - Tool call display component

---

## Task 1: DB Migration + Message Model

**Files:**
- Modify: `backend/src/tutoring/db/models.py` (Message class)

**Interfaces:**
- Produces: `Message` model with `tool_name`, `tool_input`, `tool_output` fields

- [ ] **Step 1: Run ALTER TABLE on the database**

```bash
PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db -c "
ALTER TABLE message ADD COLUMN IF NOT EXISTS tool_name TEXT;
ALTER TABLE message ADD COLUMN IF NOT EXISTS tool_input JSON;
ALTER TABLE message ADD COLUMN IF NOT EXISTS tool_output TEXT;
"
```

- [ ] **Step 2: Add fields to Message model in models.py**

In `backend/src/tutoring/db/models.py`, add three fields to the `Message` class after `content`:

```python
    role: str = Field(max_length=20)  # user/agent/tool
    content: str = Field(sa_column=Column(Text))
    tool_name: str | None = Field(default=None, max_length=100)
    tool_input: dict | None = Field(default=None, sa_column=Column(JSON))
    tool_output: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
```

- [ ] **Step 3: Verify DB columns exist**

```bash
PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db -c "\d message"
```

Expected: `tool_name`, `tool_input`, `tool_output` columns present.

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/db/models.py
git commit -m "feat: add tool fields to Message model"
```

---

## Task 2: Backend Repos - New Functions

**Files:**
- Modify: `backend/src/tutoring/db/repos.py`

**Interfaces:**
- Produces: `save_tool_message()`, `get_last_message()`

- [ ] **Step 1: Add `save_tool_message` after `save_message`**

```python
async def save_tool_message(
    session: AsyncSession, *, session_id: UUID, tool_name: str,
    tool_input: dict | None, tool_output: str | None,
) -> Message:
    obj = Message(
        session_id=session_id, role="tool", content="",
        tool_name=tool_name, tool_input=tool_input, tool_output=tool_output,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
```

- [ ] **Step 2: Add `get_last_message` after `list_messages`**

```python
async def get_last_message(session: AsyncSession, session_id: UUID) -> Message | None:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()
```

- [ ] **Step 3: Verify imports are present**

Ensure `Message` is imported at the top of `repos.py`:
```python
from tutoring.db.models import AuthToken, Project, Session, Message, Question, User
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/db/repos.py
git commit -m "feat: add save_tool_message and get_last_message repos"
```

---

## Task 3: Backend Schemas

**Files:**
- Modify: `backend/src/tutoring/chat/schemas.py`

**Interfaces:**
- Produces: `HistoryItemOut`, `HistoryOut`, updated `SendMessageRequest` with `retry` field, updated `MessageOut` with tool fields

- [ ] **Step 1: Add tool fields to `MessageOut`**

Replace the `MessageOut` class:

```python
class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str
    content: str
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    created_at: datetime
```

- [ ] **Step 2: Add `retry` to `SendMessageRequest`**

```python
class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    retry: bool = False
```

- [ ] **Step 3: Add `HistoryOut` at the end of the file**

```python
class HistoryItemOut(BaseModel):
    type: str  # "message" | "quiz"
    data: dict  # MessageOut or QuestionOut as dict


class HistoryOut(BaseModel):
    items: list[HistoryItemOut]
    pending_quiz: dict | None = None
    processing: bool = False
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/chat/schemas.py
git commit -m "feat: add HistoryOut schema and retry field"
```

---

## Task 4: Backend Service - Fix Bugs + New Functions

**Files:**
- Modify: `backend/src/tutoring/chat/service.py`

**Interfaces:**
- Consumes: `repos.save_tool_message`, `repos.get_last_message`, `repos.list_messages`, `repos.list_questions`
- Produces: Fixed `stream_chat_events`, `resume_quiz_events`, new `save_tool_messages`, `build_history`, `sync_checkpoint_to_db`

- [ ] **Step 1: Add imports at top of service.py**

```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
```

- [ ] **Step 2: Fix `stream_chat_events` - save before interrupt + tool_start events**

Replace the body of `stream_chat_events` (from `config = _stream_config(session_id)` through the end of the function) with:

```python
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if tc["name"] != "present_question":
                        yield {"event": "tool_start", "data": {
                            "tool_name": tc["name"],
                            "tool_input": tc["args"],
                        }}
            async for token in message.text:
                yield {"event": "text", "data": {"content": token}}

        if await stream.interrupted():
            await save_final_agent_message(agent, config, db_session, session_id)
            await save_tool_messages(agent, config, db_session, session_id)
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield {"event": "quiz_interrupt", "data": it.value}
            yield {"event": "done", "data": {}}
            return

        await save_final_agent_message(agent, config, db_session, session_id)
        await save_tool_messages(agent, config, db_session, session_id)
        yield {"event": "done", "data": {}}
    except Exception as e:
        logger.exception("stream_chat_events failed")
        yield {"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}}
```

- [ ] **Step 3: Fix `resume_quiz_events` - same pattern**

Replace the body of `resume_quiz_events` (from `config = _stream_config(session_id)` through the end) with:

```python
    config = _stream_config(session_id)
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""

    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if tc["name"] != "present_question":
                        yield {"event": "tool_start", "data": {
                            "tool_name": tc["name"],
                            "tool_input": tc["args"],
                        }}
            async for token in message.text:
                yield {"event": "text", "data": {"content": token}}

        if await stream.interrupted():
            await save_final_agent_message(agent, config, db_session, session_id)
            await save_tool_messages(agent, config, db_session, session_id)
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield {"event": "quiz_interrupt", "data": it.value}
            yield {"event": "done", "data": {}}
            return

        await save_final_agent_message(agent, config, db_session, session_id)
        await save_tool_messages(agent, config, db_session, session_id)
        yield {"event": "done", "data": {}}
    except Exception as e:
        logger.exception("resume_quiz_events failed")
        yield {"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}}
```

- [ ] **Step 4: Add `save_tool_messages` function after `save_final_agent_message`**

```python
async def save_tool_messages(
    agent: CompiledStateGraph,
    config: dict,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """Extract ToolMessages from checkpoint and persist to DB."""
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    existing = await repos.list_messages(db_session, session_id)
    existing_tool_ids = {m.tool_name for m in existing if m.role == "tool"}

    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.tool_call_id not in existing_tool_ids:
            tool_name = msg.name or "unknown"
            tool_input = None
            tool_output = msg.text
            await repos.save_tool_message(
                db_session, session_id=session_id,
                tool_name=tool_name, tool_input=tool_input, tool_output=tool_output,
            )
```

- [ ] **Step 5: Add `sync_checkpoint_to_db` function**

```python
async def sync_checkpoint_to_db(
    agent: CompiledStateGraph,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """Sync messages from LangGraph checkpoint to DB if missing."""
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    db_msgs = await repos.list_messages(db_session, session_id)
    db_contents = {m.content for m in db_msgs if m.role in ("user", "agent")}

    for msg in messages:
        text = msg.text or ""
        if text and text not in db_contents:
            if isinstance(msg, AIMessage):
                await repos.save_message(db_session, session_id=session_id, role="agent", content=text)
                db_contents.add(text)
            elif isinstance(msg, HumanMessage) and text not in db_contents:
                await repos.save_message(db_session, session_id=session_id, role="user", content=text)
                db_contents.add(text)
```

- [ ] **Step 6: Add `build_history` function**

```python
async def build_history(
    agent: CompiledStateGraph,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> dict:
    """Build unified timeline from DB + checkpoint. Returns {items, pending_quiz, processing}."""
    await sync_checkpoint_to_db(agent, db_session, session_id)

    messages = await repos.list_messages(db_session, session_id)
    questions = await repos.list_questions(db_session, session_id)

    items: list[dict] = []
    for m in messages:
        items.append({"type": "message", "data": {
            "id": str(m.id), "session_id": str(m.session_id),
            "role": m.role, "content": m.content,
            "tool_name": m.tool_name, "tool_input": m.tool_input,
            "tool_output": m.tool_output,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }})
    for q in questions:
        items.append({"type": "quiz", "data": {
            "id": str(q.id), "session_id": str(q.session_id),
            "topic": q.topic, "q_type": q.q_type, "stem": q.stem,
            "options": q.options, "answer": q.answer,
            "analysis": q.analysis, "status": q.status,
            "user_answer": q.user_answer,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "answered_at": q.answered_at.isoformat() if q.answered_at else None,
        }})

    items.sort(key=lambda x: x["data"]["created_at"] or "")

    pending_quiz = None
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    if state.next:
        try:
            interrupts = await agent.aget_interrupts(config)
            if interrupts:
                pending_quiz = interrupts[0].value
        except Exception:
            pass

    return {"items": items, "pending_quiz": pending_quiz, "processing": False}
```

- [ ] **Step 7: Verify backend starts**

```bash
cd backend && uv run python -c "from tutoring.chat import service; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/src/tutoring/chat/service.py
git commit -m "feat: fix agent text loss, add tool_start events, build_history, checkpoint sync"
```

---

## Task 5: Backend Router - History API + Delete Old + Retry

**Files:**
- Modify: `backend/src/tutoring/chat/router.py`
- Modify: `backend/src/tutoring/chat/sse.py`

**Interfaces:**
- Consumes: `service.build_history`, `service.get_running_task` (later), `repos.get_last_message`, `SendMessageRequest.retry`
- Produces: `GET /sessions/{id}/history`, deleted `/messages` + `/questions`, `POST /messages` with retry

- [ ] **Step 1: Update router.py imports**

Add to the imports in `router.py`:

```python
from tutoring.chat.schemas import (
    HistoryOut,
    SessionCreate,
    SessionOut,
    SendMessageRequest,
)
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db
```

Add `get_agent` to the deps import (it already exists in `core/deps.py`).

- [ ] **Step 2: Add History endpoint in router.py**

Add after the `end_session` endpoint:

```python
@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
) -> HistoryOut:
    await chat_service.get_readable_session(db_session, session_id, user)
    result = await chat_service.build_history(agent, db_session, session_id)
    return HistoryOut(**result)
```

Add `CompiledStateGraph` import:
```python
from langgraph.graph.state import CompiledStateGraph
```

- [ ] **Step 3: Delete old `list_messages` and `list_questions` endpoints**

Remove the entire `list_messages` function and the entire `list_questions` function from `router.py`.

- [ ] **Step 4: Update `send_message` in sse.py to support retry**

In `sse.py`, update the `send_message` function. Replace the user message save block:

```python
    if body.retry:
        last = await repos.get_last_message(db_session, session_id)
        if not (last and last.role == "user" and last.content == body.content):
            await repos.save_message(
                db_session, session_id=session_id, role="user", content=body.content
            )
    else:
        await repos.save_message(
            db_session, session_id=session_id, role="user", content=body.content
        )
    await repos.touch_session(db_session, session_id)
```

- [ ] **Step 5: Add `raw_stream` finally block for SSE resilience**

In `sse.py`, update the `raw_stream` inner function in `send_message`:

```python
    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for event in chat_service.stream_chat_events(
                agent, session_id, body.content, ctx, db_session
            ):
                yield _sse(event["event"], event["data"]).encode("utf-8")
        finally:
            try:
                await chat_service.save_final_agent_message(
                    agent, chat_service._stream_config(session_id), db_session, session_id
                )
                await chat_service.save_tool_messages(
                    agent, chat_service._stream_config(session_id), db_session, session_id
                )
            except Exception:
                pass
            await repos.touch_session(db_session, session_id)
```

Do the same for `resume_quiz_endpoint`'s `raw_stream`.

- [ ] **Step 6: Verify backend starts**

```bash
cd backend && uv run python -c "from tutoring.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Test with curl**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"teacher1","password":"teacher123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
SESSION="a8a8af23-dc46-4433-aaa3-1a0cf1c9d63e"
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -30
```

Expected: JSON with `items` array and `pending_quiz` field.

- [ ] **Step 8: Commit**

```bash
git add backend/src/tutoring/chat/router.py backend/src/tutoring/chat/sse.py
git commit -m "feat: add History API, delete old endpoints, add retry support, raw_stream finally"
```

---

## Task 6: Frontend Types + API Client

**Files:**
- Modify: `frontend/src/types/message.ts`
- Modify: `frontend/src/types/session.ts`
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/api/sessions.ts`
- Modify: `frontend/src/api/chat.ts`

**Interfaces:**
- Produces: Updated `MessageOut` with tool fields, `HistoryResponse` type, `sessionsApi.getHistory()`, `streamMessage` with retry param

- [ ] **Step 1: Update `frontend/src/types/message.ts`**

```typescript
export interface MessageOut {
  id: string
  session_id: string
  role: 'user' | 'agent' | 'tool'
  content: string
  tool_name?: string | null
  tool_input?: Record<string, unknown> | null
  tool_output?: string | null
  created_at: string
}
```

- [ ] **Step 2: Update `frontend/src/types/session.ts`**

Add `HistoryResponse` at the end:

```typescript
import type { ChatItem } from './chat'
import type { QuizInterruptData } from './question'

export interface HistoryResponse {
  items: ChatItem[]
  pending_quiz: QuizInterruptData | null
  processing: boolean
}
```

- [ ] **Step 3: Update `frontend/src/types/chat.ts`**

Remove the streaming variant from `ChatItem`:

```typescript
import type { MessageOut } from './message'
import type { QuestionOut } from './question'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type ChatItem =
  | { type: 'message'; data: MessageOut }
  | { type: 'quiz'; data: QuestionOut }
```

- [ ] **Step 4: Update `frontend/src/api/sessions.ts`**

Replace `listMessages` and `listQuestions` with `getHistory`:

```typescript
import { apiClient } from './client'
import type { SessionOut, SessionCreate } from '@/types/session'
import type { HistoryResponse } from '@/types/session'

export const sessionsApi = {
  list: async (params?: { status?: string; mode?: string; limit?: number; offset?: number }) => {
    const { data } = await apiClient.get<SessionOut[]>('/sessions', { params })
    return data
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<SessionOut>(`/sessions/${id}`)
    return data
  },
  create: async (body: SessionCreate) => {
    const { data } = await apiClient.post<SessionOut>('/sessions', body)
    return data
  },
  delete: async (id: string) => {
    await apiClient.delete(`/sessions/${id}`)
  },
  getHistory: async (id: string) => {
    const { data } = await apiClient.get<HistoryResponse>(`/sessions/${id}/history`)
    return data
  },
}
```

- [ ] **Step 5: Update `frontend/src/api/chat.ts` - add retry param**

```typescript
export async function* streamMessage(
  sessionId: string,
  content: string,
  signal?: AbortSignal,
  retry: boolean = false,
): AsyncGenerator<SSEEvent> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content, retry }),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  yield* parseSSE(res)
}
```

- [ ] **Step 6: Verify frontend compiles**

```bash
cd frontend && bun run typecheck
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/ frontend/src/api/
git commit -m "feat: update frontend types and API client for unified history"
```

---

## Task 7: Frontend Chat Store - P0 Changes

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**Interfaces:**
- Consumes: `sessionsApi.getHistory`, `streamMessage` with retry param
- Produces: Updated `selectSession`, fixed `done` handler, `tool_start` handler, `recoverFromHistory`, `retryLastMessage`

- [ ] **Step 1: Update `selectSession` to use getHistory**

Replace the `selectSession` method:

```typescript
  selectSession: async id => {
    set({ loadingSession: true, streamStatus: 'idle', pendingQuiz: null, streamingContent: '', lastError: null })
    try {
      const [session, history] = await Promise.all([
        sessionsApi.get(id),
        sessionsApi.getHistory(id),
      ])
      set({
        currentSession: session,
        items: history.items,
        pendingQuiz: history.pending_quiz,
        streamStatus: history.pending_quiz ? 'quiz_interrupted' : 'idle',
      })
    } finally {
      set({ loadingSession: false })
    }
  },
```

- [ ] **Step 2: Add `recoverFromHistory` helper to the store**

Add this as a private function inside the store factory (after `clearCurrent`):

```typescript
  recoverFromHistory: async () => {
    const { currentSession } = get()
    if (!currentSession) return
    try {
      const history = await sessionsApi.getHistory(currentSession.id)
      if (history.pending_quiz) {
        set({ items: history.items, pendingQuiz: history.pending_quiz, streamStatus: 'quiz_interrupted', streamingContent: '' })
      } else if (history.processing) {
        set({ items: history.items, streamStatus: 'streaming' })
        setTimeout(() => get().recoverFromHistory(), 3000)
      } else {
        const lastAgent = [...history.items].reverse().find(i => i.type === 'message' && i.data.role === 'agent')
        if (lastAgent) {
          set({ items: history.items, streamStatus: 'idle', streamingContent: '' })
        } else {
          set({ items: history.items, streamStatus: 'error', lastError: { message: '连接中断，点击重试', code: 'RETRYABLE' }, streamingContent: '' })
        }
      }
    } catch {
      set({ streamStatus: 'error', lastError: { message: '网络错误', code: 'NETWORK' } })
    }
  },
```

Add `recoverFromHistory` to the `ChatState` interface.

- [ ] **Step 3: Update `sendMessage` - done handler to save text on quiz**

In the `done` case, replace the `quiz_interrupted` branch:

```typescript
          case 'done':
            if (get().streamStatus === 'streaming') {
              const agentMsg = {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(),
                  session_id: currentSession.id,
                  role: 'agent' as const,
                  content: get().streamingContent,
                  created_at: new Date().toISOString(),
                },
              }
              set(state => ({
                items: [...state.items, agentMsg],
                streamStatus: 'idle' as const,
                streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                const agentMsg = {
                  type: 'message' as const,
                  data: {
                    id: crypto.randomUUID(),
                    session_id: currentSession.id,
                    role: 'agent' as const,
                    content: get().streamingContent,
                    created_at: new Date().toISOString(),
                  },
                }
                set(state => ({ items: [...state.items, agentMsg], streamingContent: '' }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
```

- [ ] **Step 4: Add `tool_start` handler in `sendMessage`**

Add to the `switch (ev.event)` block:

```typescript
          case 'tool_start':
            const toolItem = {
              type: 'message' as const,
              data: {
                id: crypto.randomUUID(),
                session_id: currentSession.id,
                role: 'tool' as const,
                content: '',
                tool_name: ev.data.tool_name,
                tool_input: ev.data.tool_input,
                created_at: new Date().toISOString(),
              },
            }
            set(state => ({ items: [...state.items, toolItem] }))
            break
```

- [ ] **Step 5: Update `sendMessage` catch block for auto-recovery**

Replace the catch block:

```typescript
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        const is409 = e.message?.includes('409')
        if (is409) {
          toast.info('请先回答上方题目')
          await get().recoverFromHistory()
        } else {
          await new Promise(r => setTimeout(r, 2000))
          await get().recoverFromHistory()
        }
      }
    } finally {
      set({ currentAbort: null })
    }
```

- [ ] **Step 6: Add `retryLastMessage` to the store**

```typescript
  retryLastMessage: async () => {
    const { currentSession, items, currentAbort } = get()
    if (!currentSession) return
    const lastUserMsg = [...items].reverse().find(i => i.type === 'message' && i.data.role === 'user')
    if (!lastUserMsg || lastUserMsg.type !== 'message') return

    set({ streamStatus: 'streaming', streamingContent: '', lastError: null })
    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, lastUserMsg.data.content, ac.signal, true)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({
              items: [...state.items, {
                type: 'message' as const,
                data: {
                  id: crypto.randomUUID(), session_id: currentSession.id,
                  role: 'tool' as const, content: '',
                  tool_name: ev.data.tool_name, tool_input: ev.data.tool_input,
                  created_at: new Date().toISOString(),
                },
              }],
            }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({
                items: [...state.items, {
                  type: 'message' as const,
                  data: {
                    id: crypto.randomUUID(), session_id: currentSession.id,
                    role: 'agent' as const, content: get().streamingContent,
                    created_at: new Date().toISOString(),
                  },
                }],
                streamStatus: 'idle' as const, streamingContent: '',
              }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({
                  items: [...state.items, {
                    type: 'message' as const,
                    data: {
                      id: crypto.randomUUID(), session_id: currentSession.id,
                      role: 'agent' as const, content: get().streamingContent,
                      created_at: new Date().toISOString(),
                    },
                  }],
                  streamingContent: '',
                }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
          case 'error':
            set({ streamStatus: 'error', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        await new Promise(r => setTimeout(r, 2000))
        await get().recoverFromHistory()
      }
    } finally {
      set({ currentAbort: null })
    }
  },
```

Add `retryLastMessage` to the `ChatState` interface.

- [ ] **Step 7: Fix `submitQuiz` done handler - same pattern as sendMessage**

In the `submitQuiz` method's `done` handler, apply the same fix: when `quiz_interrupted`, save streaming content as agent message before clearing.

- [ ] **Step 8: Verify frontend compiles**

```bash
cd frontend && bun run typecheck
```

Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "feat: chat store - unified history, done handler fix, tool_start, recovery, retry"
```

---

## Task 8: Frontend ChatView + ChatInput + ToolCallBubble

**Files:**
- Modify: `frontend/src/features/chat/ChatView.tsx`
- Modify: `frontend/src/features/chat/ChatInput.tsx`
- Create: `frontend/src/features/chat/ToolCallBubble.tsx`

- [ ] **Step 1: Create `frontend/src/features/chat/ToolCallBubble.tsx`**

```tsx
import { Search } from 'lucide-react'
import type { MessageOut } from '@/types/message'

export default function ToolCallBubble({ message }: { message: MessageOut }) {
  if (message.tool_name === 'search_knowledge') {
    const query = (message.tool_input as Record<string, unknown>)?.query as string ?? ''
    return (
      <div className="flex justify-center">
        <div className="flex items-center gap-1.5 rounded-lg border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
          <Search className="size-3" />
          <span>搜索知识库: {query}</span>
        </div>
      </div>
    )
  }
  return null
}
```

- [ ] **Step 2: Update `ChatView.tsx` - scroll + tool render + hints**

Add import and update the component:

```tsx
import ToolCallBubble from './ToolCallBubble'
```

Update the scroll effect to include `pendingQuiz`:

```tsx
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, streamingContent, pendingQuiz])
```

Update the items map to render tool messages:

```tsx
        {items.map((item, idx) => {
          if (item.type === 'message') {
            if (item.data.role === 'tool') {
              return <ToolCallBubble key={idx} message={item.data} />
            }
            return <MessageBubble key={idx} message={item.data} />
          }
          if (item.type === 'quiz') {
            const q = item.data
            return (
              <QuizCard
                key={idx}
                quiz={q}
                status={q.status}
                userAnswer={q.user_answer}
                correctAnswer={q.answer}
                analysis={q.analysis}
                onSubmit={() => {}}
                onSkip={() => {}}
              />
            )
          }
          return null
        })}
```

- [ ] **Step 3: Update `ChatInput.tsx` - retry button + quiz hint**

Read the current ChatInput to understand its props, then add:
- A retry button when `streamStatus === 'error'` and `lastError?.code === 'RETRYABLE'`
- A hint text when input is disabled due to `quiz_interrupted`

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && bun run typecheck && bun run build
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/chat/
git commit -m "feat: ToolCallBubble component, scroll fix, retry button, quiz hint"
```

---

## Task 9: Backend P2 - Task Registry + Background Agent

**Files:**
- Modify: `backend/src/tutoring/chat/service.py`
- Modify: `backend/src/tutoring/chat/sse.py`

**Interfaces:**
- Produces: `_running_tasks` registry, `get_running_task()`, `run_agent_background()`, updated `build_history()` with `processing` field

- [ ] **Step 1: Add task registry to service.py**

Add at module level (after `logger`):

```python
import asyncio

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}


def get_running_task(session_id: uuid.UUID) -> asyncio.Task | None:
    task = _running_tasks.get(session_id)
    if task and not task.done():
        return task
    _running_tasks.pop(session_id, None)
    return None
```

- [ ] **Step 2: Add `run_agent_background` to service.py**

```python
async def run_agent_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory,
) -> None:
    """Run agent in background, events -> queue. Not tied to SSE connection."""
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
            async with db_session_factory() as db_session:
                await save_final_agent_message(agent, config, db_session, session_id)
                await save_tool_messages(agent, config, db_session, session_id)
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})
        else:
            async with db_session_factory() as db_session:
                await save_final_agent_message(agent, config, db_session, session_id)
                await save_tool_messages(agent, config, db_session, session_id)

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_agent_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

- [ ] **Step 3: Add `run_resume_background` for quiz resume**

```python
async def run_resume_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory,
) -> None:
    """Run quiz resume in background."""
    config = _stream_config(session_id)
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""
    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),
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
            async with db_session_factory() as db_session:
                await save_final_agent_message(agent, config, db_session, session_id)
                await save_tool_messages(agent, config, db_session, session_id)
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})
        else:
            async with db_session_factory() as db_session:
                await save_final_agent_message(agent, config, db_session, session_id)
                await save_tool_messages(agent, config, db_session, session_id)

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_resume_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

- [ ] **Step 4: Update `build_history` to include `processing`**

In `build_history`, replace the return statement:

```python
    task = get_running_task(session_id)
    processing = bool(task and not task.done())

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}
```

- [ ] **Step 5: Refactor `send_message` in sse.py to use background task**

Replace the `send_message` function body (after the session check and user message save):

```python
    if chat_service.get_running_task(session_id):
        raise AppError(409, "SESSION_PROCESSING", "Agent is already running for this session")

    ctx = await chat_service.build_agent_context(db_session, sess)

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        chat_service.run_agent_background(
            agent, session_id, body.content, ctx, queue, db_session_factory,
        )
    )
    chat_service._running_tasks[session_id] = task

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield b": heartbeat\n\n"
                    continue
                yield _sse(event["event"], event["data"]).encode("utf-8")
                if event["event"] in ("done", "error"):
                    break
        finally:
            await repos.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

Add import at top of sse.py:
```python
import asyncio
```

And get `db_session_factory` from deps - add to the function signature:
```python
from tutoring.core.deps import get_db_session_factory
```

Actually, simpler: get it from the app state or pass it. Check how `get_agent` gets its dependencies. The `db_session_factory` should be available as a dependency. Let me check `core/deps.py`.

Actually, looking at the existing code, the `get_db` dependency returns an `AsyncSession`, not a factory. The factory is created in `main.py`. I need to make the factory available as a dependency.

Add to `core/deps.py`:
```python
from tutoring.core.database import create_session_factory

# In main.py lifespan, store the factory on app.state
# In deps.py, create a dependency that reads it
```

Actually, the simplest approach: add `db_session_factory` to `app.state` and access it in the endpoint.

In `main.py` lifespan, after creating the factory:
```python
app.state.db_session_factory = session_factory
```

In `sse.py`, access it:
```python
from tutoring.main import app
db_session_factory = app.state.db_session_factory
```

Or better, add a dependency:
```python
# core/deps.py
def get_db_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.db_session_factory
```

- [ ] **Step 6: Refactor `resume_quiz_endpoint` in sse.py similarly**

Same pattern: create background task + queue consumer.

- [ ] **Step 7: Verify backend starts**

```bash
cd backend && uv run python -c "from tutoring.main import app; print('OK')"
```

- [ ] **Step 8: Test - send message, check processing status**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"teacher1","password":"teacher123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
# Create new session
SESSION=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"free"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
# Send message (non-blocking test)
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"hello"}' &
sleep 1
# Check processing status
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('processing:', d.get('processing'))"
```

- [ ] **Step 9: Commit**

```bash
git add backend/src/tutoring/chat/service.py backend/src/tutoring/chat/sse.py backend/src/tutoring/core/deps.py backend/src/tutoring/main.py
git commit -m "feat: background task - agent runs in asyncio.Task, SSE consumes from queue"
```

---

## Task 10: End-to-End Verification

**Files:**
- No file changes - verification only

- [ ] **Step 1: Restart backend**

```bash
# Kill existing uvicorn
pkill -f "uvicorn tutoring.main:app" || true
# Start fresh
cd backend && uv run uvicorn tutoring.main:app --host 0.0.0.0 --port 8000 &
```

- [ ] **Step 2: Frontend build**

```bash
cd frontend && bun run build
```

- [ ] **Step 3: Test - normal flow (free mode)**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"teacher1","password":"teacher123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
SESSION=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"free"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
# Send message
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"你好"}'
# Check history
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: History has user + agent messages, `processing: false`, `pending_quiz: null`.

- [ ] **Step 4: Test - project mode with quiz**

```bash
# Use existing project session
SESSION="a8a8af23-dc46-4433-aaa3-1a0cf1c9d63e"
# Send message that triggers quiz
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"出题考考我"}'
# Check history after quiz
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('pending_quiz:', d.get('pending_quiz')); print('items count:', len(d.get('items',[])))"
```

Expected: `pending_quiz` is non-null after quiz, agent text before quiz is in items.

- [ ] **Step 5: Test - refresh recovery**

After quiz interrupt, simulate refresh:
```bash
# History should show pending_quiz
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('pending_quiz is None:', d['pending_quiz'] is None)"
```

Expected: `pending_quiz is None: False` (quiz is recovered from checkpoint).

- [ ] **Step 6: Test - 409 on interrupted session**

```bash
curl -s -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"test"}'
```

Expected: 409 `SESSION_PROCESSING` (if agent still running) or 409 `SESSION_INTERRUPTED` (if quiz pending).

- [ ] **Step 7: Test - tool_start event visible**

In project mode, send a message that triggers knowledge search:
```bash
SESSION2=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"project","project_id":"2c700ce7-3fdc-4672-9813-ba751bdc87a6"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION2/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"安全隔离"}'
```

Expected: `event: tool_start` appears in SSE stream before text events.

- [ ] **Step 8: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: e2e verification fixes"
```

# Chat DB Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `message` + `question` tables with a single `chat_event` table (JSONB + Pydantic models), eliminate all checkpoint sync logic, make History API read-only from DB.

**Architecture:** Single `chat_event` table with `type` discriminator and JSONB `data` field. Write path (background task) accumulates data during streaming and saves to DB. Read path (History API) queries only DB. `pending_quiz` = DB query for `type='quiz' AND status='pending'`.

**Tech Stack:** FastAPI, SQLModel, Pydantic, PostgreSQL JSONB, LangGraph 1.x, React 19, Zustand 5

## Global Constraints

- DB columns use `TIMESTAMP(timezone=True)` + `server_default=func.now()`
- Python code uses `datetime.now(timezone.utc)` not `datetime.utcnow()`
- No data migration needed - old tables can be dropped (user confirmed)
- `create_all` is idempotent but does NOT alter existing tables - manual SQL needed for drops
- No comments in code unless asked
- Backend verify: `uv run python -c "from tutoring.main import app; print('OK')"`
- Frontend verify: `bun run typecheck && bun run build`
- DB: `PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db`

## File Structure

**Backend - modify:**
- `backend/src/tutoring/db/models.py` - Replace Message+Question with ChatEvent
- `backend/src/tutoring/db/repos.py` - Replace message+question repos with event repos
- `backend/src/tutoring/chat/schemas.py` - Replace MessageOut+QuestionOut with ChatEventOut
- `backend/src/tutoring/chat/service.py` - Remove sync logic, rewrite build_history + run_agent_background
- `backend/src/tutoring/chat/sse.py` - Update to use new repos
- `backend/src/tutoring/chat/router.py` - Update history endpoint
- `backend/src/tutoring/agent/tools.py` - Update present_question to use new repos

**Backend - create:**
- (nothing new - all changes in existing files)

**Frontend - modify:**
- `frontend/src/types/message.ts` - Replace with ChatEvent types
- `frontend/src/types/session.ts` - Update HistoryResponse
- `frontend/src/types/chat.ts` - Simplify to use ChatEvent
- `frontend/src/types/question.ts` - Delete (merged into ChatEvent)
- `frontend/src/api/sessions.ts` - Update getHistory
- `frontend/src/api/chat.ts` - No change
- `frontend/src/stores/chat.ts` - Update to use ChatEvent
- `frontend/src/features/chat/ChatView.tsx` - Render by event.type
- `frontend/src/features/chat/MessageBubble.tsx` - Accept ChatEvent
- `frontend/src/features/chat/QuizCard.tsx` - Accept ChatEvent
- `frontend/src/features/chat/ToolCallBubble.tsx` - Accept ChatEvent

---

## Task 1: DB - Drop Old Tables, Create chat_event

**Files:**
- Modify: `backend/src/tutoring/db/models.py`

**Interfaces:**
- Produces: `ChatEvent` SQLModel

- [ ] **Step 1: Drop old tables and create new**

```bash
PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db -c "
DROP TABLE IF EXISTS message CASCADE;
DROP TABLE IF EXISTS question CASCADE;
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
"
```

- [ ] **Step 2: Replace Message + Question models with ChatEvent in models.py**

Delete the `Message` class and `Question` class. Add:

```python
class ChatEvent(SQLModel, table=True):
    """统一聊天事件表。type 区分 user/agent/tool/quiz。"""
    __tablename__ = "chat_event"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    session_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("session.id", ondelete="CASCADE"),
            index=True,
        ),
    )
    type: str = Field(max_length=20)  # user/agent/tool/quiz
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    content: str | None = Field(default=None, sa_column=Column(Text))
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str | None = Field(default=None, max_length=20)  # quiz: pending/answered/skipped
    answered_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    session: "Session" = Relationship(back_populates="events")
```

Update `Session` model's relationships: replace `messages` and `questions` with `events`:

```python
    events: list["ChatEvent"] = Relationship(back_populates="session", cascade_delete=True)
```

Remove `messages` and `questions` relationships from Session.

- [ ] **Step 3: Verify DB**

```bash
PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db -c "\d chat_event"
```

Expected: Table with `id`, `session_id`, `type`, `created_at`, `content`, `data`, `status`, `answered_at`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/db/models.py
git commit -m "refactor: replace Message+Question with ChatEvent model"
```

---

## Task 2: Pydantic Data Models + Repos

**Files:**
- Modify: `backend/src/tutoring/db/repos.py`

**Interfaces:**
- Produces: `save_event()`, `list_events()`, `update_quiz_status()`, `has_pending_quiz()`, `get_last_user_event()`

- [ ] **Step 1: Add Pydantic data models at top of repos.py**

```python
from typing import Literal
from pydantic import BaseModel


class ToolEventData(BaseModel):
    tool_name: str
    tool_input: dict | None = None
    tool_output: str | None = None


class QuizEventData(BaseModel):
    topic: str
    q_type: Literal["single", "multi", "short"]
    stem: str
    options: list[str] | None = None
    answer: str
    analysis: str | None = None
    user_answer: str | None = None
```

- [ ] **Step 2: Replace Message+Question repos with ChatEvent repos**

Delete all `=== Message ===` and `=== Question ===` sections. Replace with:

```python
# === ChatEvent ===

async def save_event(
    session: AsyncSession, *, session_id: UUID, type: str,
    content: str | None = None, data: dict | None = None,
    status: str | None = None,
) -> ChatEvent:
    obj = ChatEvent(
        session_id=session_id, type=type, content=content,
        data=data, status=status,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_events(session: AsyncSession, session_id: UUID) -> list[ChatEvent]:
    stmt = (
        select(ChatEvent)
        .where(ChatEvent.session_id == session_id)
        .order_by(ChatEvent.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_quiz_status(
    session: AsyncSession, event_id: UUID, *,
    status: str, user_answer: str | None = None,
) -> None:
    from datetime import datetime, timezone
    existing = await session.get(ChatEvent, event_id)
    if existing and existing.data:
        existing.data["user_answer"] = user_answer
    existing.status = status
    existing.answered_at = datetime.now(timezone.utc)
    await session.commit()


async def has_pending_quiz(session: AsyncSession, session_id: UUID) -> bool:
    from sqlalchemy import exists as sa_exists
    stmt = (
        select(sa_exists(ChatEvent))
        .where(
            ChatEvent.session_id == session_id,
            ChatEvent.type == "quiz",
            ChatEvent.status == "pending",
        )
    )
    result = await session.execute(stmt)
    return result.scalar()


async def get_last_user_event(session: AsyncSession, session_id: UUID) -> ChatEvent | None:
    stmt = (
        select(ChatEvent)
        .where(ChatEvent.session_id == session_id, ChatEvent.type == "user")
        .order_by(ChatEvent.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()
```

Update imports: replace `Message, Question` with `ChatEvent`.

- [ ] **Step 3: Verify backend compiles**

```bash
cd backend && uv run python -c "from tutoring.db import repos; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/db/repos.py
git commit -m "refactor: replace message+question repos with chat_event repos"
```

---

## Task 3: Schemas + Service Rewrite

**Files:**
- Modify: `backend/src/tutoring/chat/schemas.py`
- Modify: `backend/src/tutoring/chat/service.py`

**Interfaces:**
- Consumes: `repos.save_event`, `repos.list_events`, `repos.update_quiz_status`, `repos.has_pending_quiz`, `repos.get_last_user_event`, `repos.ToolEventData`, `repos.QuizEventData`
- Produces: `ChatEventOut`, `HistoryOut`, rewritten `build_history()`, `run_agent_background()`, `is_interrupted()`

- [ ] **Step 1: Rewrite schemas.py**

Replace `MessageOut`, `QuestionOut`, `HistoryItemOut` with:

```python
class ChatEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    type: str
    created_at: datetime
    content: str | None = None
    data: dict | None = None
    status: str | None = None
    answered_at: datetime | None = None


class HistoryOut(BaseModel):
    items: list[ChatEventOut]
    pending_quiz: ChatEventOut | None = None
    processing: bool = False
```

Keep `SessionCreate`, `SessionOut`, `SendMessageRequest`, `QuizResumeRequest` unchanged.

- [ ] **Step 2: Rewrite service.py - remove all sync/final save functions**

Delete these functions entirely:
- `sync_checkpoint_to_db`
- `sync_tool_messages`
- `save_final_agent_message`
- `save_tool_messages`
- `build_history` (will be rewritten)

Delete imports of `AIMessage`, `ToolMessage` from `langchain_core.messages` (no longer needed in service).

- [ ] **Step 3: Rewrite `is_interrupted` - DB only, no checkpoint**

```python
async def is_interrupted(db: AsyncSession, session_id: uuid.UUID) -> bool:
    return await repos.has_pending_quiz(db, session_id)
```

- [ ] **Step 4: Rewrite `build_history` - DB only, no checkpoint**

```python
async def build_history(
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> dict:
    events = await repos.list_events(db_session, session_id)
    items = [_event_to_dict(e) for e in events]

    pending_quiz = None
    for e in events:
        if e.type == "quiz" and e.status == "pending":
            pending_quiz = _event_to_dict(e)
            break

    task = get_running_task(session_id)
    processing = bool(task and not task.done())

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}


def _event_to_dict(e) -> dict:
    return {
        "id": str(e.id),
        "session_id": str(e.session_id),
        "type": e.type,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "content": e.content,
        "data": e.data,
        "status": e.status,
        "answered_at": e.answered_at.isoformat() if e.answered_at else None,
    }
```

- [ ] **Step 5: Rewrite `run_agent_background` - accumulate during stream, save after**

```python
async def run_agent_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory,
) -> None:
    import inspect
    from langchain_core.messages import ToolMessage

    config = _stream_config(session_id)
    full_text = ""
    pending_tools: list[tuple[str, dict | None]] = []
    completed_tools: list[tuple[str, dict | None, str]] = []

    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config, version="v3", context=context,
        )
        async for message in stream.messages:
            if isinstance(message, ToolMessage):
                if pending_tools:
                    name, args = pending_tools.pop(0)
                    completed_tools.append((name, args, message.text or ""))
                continue

            tc = getattr(message, "tool_calls", None)
            if tc and not inspect.isawaitable(tc):
                try:
                    for call in tc:
                        name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
                        args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                        if name and name != "present_question":
                            await queue.put({"event": "tool_start", "data": {
                                "tool_name": name, "tool_input": args,
                            }})
                            pending_tools.append((name, args))
                except TypeError:
                    pass

            async for token in message.text:
                full_text += token
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        async with db_session_factory() as db_session:
            if full_text:
                await repos.save_event(
                    db_session, session_id=session_id, type="agent", content=full_text,
                )
            for name, args, output in completed_tools:
                data = repos.ToolEventData(
                    tool_name=name, tool_input=args, tool_output=output,
                ).model_dump()
                await repos.save_event(
                    db_session, session_id=session_id, type="tool", data=data,
                )

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_agent_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

- [ ] **Step 6: Rewrite `run_resume_background` - same pattern**

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
    import inspect
    from langchain_core.messages import ToolMessage

    config = _stream_config(session_id)
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""

    full_text = ""
    pending_tools: list[tuple[str, dict | None]] = []
    completed_tools: list[tuple[str, dict | None, str]] = []

    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),
            config=config, version="v3", context=context,
        )
        async for message in stream.messages:
            if isinstance(message, ToolMessage):
                if pending_tools:
                    name, args = pending_tools.pop(0)
                    completed_tools.append((name, args, message.text or ""))
                continue

            tc = getattr(message, "tool_calls", None)
            if tc and not inspect.isawaitable(tc):
                try:
                    for call in tc:
                        name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
                        args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                        if name and name != "present_question":
                            await queue.put({"event": "tool_start", "data": {
                                "tool_name": name, "tool_input": args,
                            }})
                            pending_tools.append((name, args))
                except TypeError:
                    pass

            async for token in message.text:
                full_text += token
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        async with db_session_factory() as db_session:
            if full_text:
                await repos.save_event(
                    db_session, session_id=session_id, type="agent", content=full_text,
                )
            for name, args, output in completed_tools:
                data = repos.ToolEventData(
                    tool_name=name, tool_input=args, tool_output=output,
                ).model_dump()
                await repos.save_event(
                    db_session, session_id=session_id, type="tool", data=data,
                )

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_resume_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

- [ ] **Step 7: Keep `stream_chat_events` and `resume_quiz_events` for backward compat**

These functions are no longer called by the SSE endpoints (which use background tasks), but keep them as thin wrappers or delete them if nothing else uses them. Check with grep. If nothing uses them, delete.

- [ ] **Step 8: Verify backend compiles**

```bash
cd backend && uv run python -c "from tutoring.chat import service; print('OK')"
```

- [ ] **Step 9: Commit**

```bash
git add backend/src/tutoring/chat/schemas.py backend/src/tutoring/chat/service.py
git commit -m "refactor: remove sync logic, rewrite build_history + run_agent_background for chat_event"
```

---

## Task 4: SSE + Router + Tools

**Files:**
- Modify: `backend/src/tutoring/chat/sse.py`
- Modify: `backend/src/tutoring/chat/router.py`
- Modify: `backend/src/tutoring/agent/tools.py`

**Interfaces:**
- Consumes: `service.build_history`, `service.is_interrupted`, `service.run_agent_background`, `service.run_resume_background`, `repos.save_event`, `repos.update_quiz_status`, `repos.has_pending_quiz`, `repos.get_last_user_event`
- Produces: Updated `send_message`, `resume_quiz_endpoint`, `get_history`, `present_question` tool

- [ ] **Step 1: Update sse.py - send_message uses new repos**

In `send_message`, replace the user message save:

```python
    if body.retry:
        existing = await repos.list_events(db_session, session_id)
        already_saved = any(e.type == "user" and e.content == body.content for e in existing)
        if not already_saved:
            await repos.save_event(
                db_session, session_id=session_id, type="user", content=body.content,
            )
    else:
        await repos.save_event(
            db_session, session_id=session_id, type="user", content=body.content,
        )
```

Replace `is_interrupted` call (now takes db, not agent):

```python
    if await chat_service.is_interrupted(db_session, session_id):
        raise AppError(
            409, "SESSION_INTERRUPTED",
            "Session is paused at a quiz; call /quiz/resume first",
        )
```

Remove `agent` parameter from `is_interrupted` call (it no longer needs agent).

- [ ] **Step 2: Update sse.py - resume_quiz uses new repos**

In `resume_quiz_endpoint`, replace `is_interrupted` call:

```python
    if not await chat_service.is_interrupted(db_session, session_id):
        raise AppError(
            409, "SESSION_NOT_INTERRUPTED",
            "Session is not paused; no quiz to resume",
        )
```

- [ ] **Step 3: Update router.py - get_history uses new build_history**

```python
@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> HistoryOut:
    await chat_service.get_readable_session(db_session, session_id, user)
    result = await chat_service.build_history(db_session, session_id)
    return HistoryOut(**result)
```

Note: `build_history` no longer takes `agent` parameter. Remove `agent` dependency from the endpoint.

- [ ] **Step 4: Update tools.py - present_question uses new repos**

Replace `upsert_pending_question` and `update_question` calls:

```python
    async def present_question(
        topic: str,
        q_type: Literal["single", "multi", "short"],
        stem: str,
        options: list[str] | None,
        answer: str,
        analysis: str,
        config: RunnableConfig,
    ) -> dict:
        from langgraph.types import interrupt

        session_id = UUID(config["configurable"]["thread_id"])

        quiz_data = repos.QuizEventData(
            topic=topic, q_type=q_type, stem=stem,
            options=options, answer=answer, analysis=analysis,
        ).model_dump()

        async with _db_session() as db_session:
            quiz_event = await repos.save_event(
                db_session, session_id=session_id,
                type="quiz", data=quiz_data, status="pending",
            )

        student_answer = interrupt(
            {
                "question_id": str(quiz_event.id),
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        if student_answer.get("action") == "skip":
            async with _db_session() as db_session:
                await repos.update_quiz_status(
                    db_session, quiz_event.id, status="skipped",
                )
            return {"question_id": str(quiz_event.id), "action": "skipped"}

        user_answer = student_answer.get("answer", "")
        async with _db_session() as db_session:
            await repos.update_quiz_status(
                db_session, quiz_event.id,
                status="answered", user_answer=user_answer,
            )

        return {"question_id": str(quiz_event.id), "student_answer": user_answer}
```

- [ ] **Step 5: Verify backend compiles and starts**

```bash
cd backend && uv run python -c "from tutoring.main import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/tutoring/chat/sse.py backend/src/tutoring/chat/router.py backend/src/tutoring/agent/tools.py
git commit -m "refactor: update SSE, router, tools for chat_event table"
```

---

## Task 5: Frontend Types + API + Store

**Files:**
- Modify: `frontend/src/types/message.ts` (rename content to ChatEvent)
- Delete: `frontend/src/types/question.ts`
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/types/session.ts`
- Modify: `frontend/src/api/sessions.ts`
- Modify: `frontend/src/stores/chat.ts`

**Interfaces:**
- Produces: `ChatEvent`, `ToolEventData`, `QuizEventData`, `HistoryResponse`, updated `sessionsApi`, updated `useChatStore`

- [ ] **Step 1: Replace `frontend/src/types/message.ts` with ChatEvent types**

```typescript
export interface ToolEventData {
  tool_name: string
  tool_input: Record<string, unknown> | null
  tool_output: string | null
}

export interface QuizEventData {
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
  answer: string
  analysis: string | null
  user_answer: string | null
}

export interface ChatEvent {
  id: string
  session_id: string
  type: 'user' | 'agent' | 'tool' | 'quiz'
  created_at: string
  content: string | null
  data: ToolEventData | QuizEventData | null
  status: 'pending' | 'answered' | 'skipped' | null
  answered_at: string | null
}

// For SSE quiz_interrupt event
export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
```

- [ ] **Step 2: Delete `frontend/src/types/question.ts`**

```bash
rm frontend/src/types/question.ts
```

- [ ] **Step 3: Update `frontend/src/types/chat.ts`**

```typescript
import type { ChatEvent } from './message'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type ChatItem = ChatEvent
```

- [ ] **Step 4: Update `frontend/src/types/session.ts`**

```typescript
import type { ChatEvent, QuizInterruptData } from './message'

export interface SessionOut {
  id: string
  user_id: string
  mode: 'free' | 'project'
  project_id: string | null
  project_name: string | null
  title: string | null
  last_active_at: string
  created_at: string
}

export interface SessionCreate {
  mode: 'free' | 'project'
  project_id?: string
}

export interface HistoryResponse {
  items: ChatEvent[]
  pending_quiz: ChatEvent | null
  processing: boolean
}
```

- [ ] **Step 5: Fix all imports that referenced `question.ts`**

Search and replace:
- `import type { QuestionOut } from '@/types/question'` -> `import type { ChatEvent, QuizInterruptData } from '@/types/message'`
- `QuestionOut` -> `ChatEvent`
- `QuizInterruptData` import from `@/types/message` instead of `@/types/question`

- [ ] **Step 6: Update `frontend/src/api/sessions.ts`**

No changes needed - `getHistory` already returns `HistoryResponse`.

- [ ] **Step 7: Update `frontend/src/stores/chat.ts`**

Key changes:
- `items` type: `ChatEvent[]` instead of `ChatItem[]`
- `pendingQuiz` type: `ChatEvent | null` instead of `QuizInterruptData | null`
- `sendMessage`: user message is `ChatEvent` with `type: 'user'`
- `sendMessage`: agent message is `ChatEvent` with `type: 'agent'`
- `sendMessage`: tool_start creates `ChatEvent` with `type: 'tool'`
- `selectSession`: `pending_quiz` is now `ChatEvent`, check `type === 'quiz' && status === 'pending'`
- `submitQuiz`: quiz card data is `ChatEvent`, create quiz `ChatEvent` with `type: 'quiz'`

The store logic stays the same, just the types change. Replace all `ChatItem` references with `ChatEvent`, and update the object shapes:

For user message:
```typescript
const userMsg: ChatEvent = {
  id: crypto.randomUUID(),
  session_id: currentSession.id,
  type: 'user',
  created_at: new Date().toISOString(),
  content,
  data: null,
  status: null,
  answered_at: null,
}
```

For agent message:
```typescript
const agentMsg: ChatEvent = {
  id: crypto.randomUUID(),
  session_id: currentSession.id,
  type: 'agent',
  created_at: new Date().toISOString(),
  content: get().streamingContent,
  data: null,
  status: null,
  answered_at: null,
}
```

For tool item:
```typescript
const toolItem: ChatEvent = {
  id: crypto.randomUUID(),
  session_id: currentSession.id,
  type: 'tool',
  created_at: new Date().toISOString(),
  content: null,
  data: {
    tool_name: ev.data.tool_name,
    tool_input: ev.data.tool_input,
    tool_output: null,
  },
  status: null,
  answered_at: null,
}
```

For quiz in submitQuiz done handler:
```typescript
const quizEvent: ChatEvent = {
  id: pendingQuiz.id,
  session_id: currentSession.id,
  type: 'quiz',
  created_at: pendingQuiz.created_at,
  content: null,
  data: {
    ...pendingQuiz.data,
    user_answer: action === 'skip' ? null : (answer ?? null),
  } as QuizEventData,
  status: action === 'skip' ? 'skipped' : 'answered',
  answered_at: new Date().toISOString(),
}
```

- [ ] **Step 8: Verify frontend compiles**

```bash
cd frontend && bun run typecheck
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/ frontend/src/api/ frontend/src/stores/
git commit -m "refactor: frontend types + store for ChatEvent"
```

---

## Task 6: Frontend Components

**Files:**
- Modify: `frontend/src/features/chat/ChatView.tsx`
- Modify: `frontend/src/features/chat/MessageBubble.tsx`
- Modify: `frontend/src/features/chat/QuizCard.tsx`
- Modify: `frontend/src/features/chat/ToolCallBubble.tsx`
- Modify: `frontend/src/features/students/StudentChatViewer.tsx`

**Interfaces:**
- Consumes: `ChatEvent` type from Task 5

- [ ] **Step 1: Update `MessageBubble.tsx` to accept `ChatEvent`**

Change the props interface from `MessageOut` to `ChatEvent`:

```typescript
import type { ChatEvent } from '@/types/message'

interface MessageBubbleProps {
  message: ChatEvent
}
```

The component reads `message.content` and `message.type` (for user vs agent styling). No other changes needed.

- [ ] **Step 2: Update `QuizCard.tsx` to accept `ChatEvent`**

Change props from `QuestionOut | QuizInterruptData` to `ChatEvent`:

```typescript
import type { ChatEvent, QuizEventData } from '@/types/message'

interface QuizCardProps {
  quiz: ChatEvent
  status: 'pending' | 'answered' | 'skipped'
  userAnswer?: string | null
  correctAnswer?: string
  analysis?: string | null
  onSubmit: (answer: string) => void
  onSkip: () => void
}
```

Extract quiz fields from `quiz.data as QuizEventData`:

```typescript
const q = quiz.data as QuizEventData
const qType = q.q_type
const options = q.options ?? []
const stem = q.stem
const topic = q.topic
```

- [ ] **Step 3: Update `ToolCallBubble.tsx` to accept `ChatEvent`**

```typescript
import type { ChatEvent, ToolEventData } from '@/types/message'

export default function ToolCallBubble({ message }: { message: ChatEvent }) {
  const data = message.data as ToolEventData
  if (data?.tool_name === 'search_knowledge') {
    const query = (data.tool_input as Record<string, unknown>)?.query as string ?? ''
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

- [ ] **Step 4: Update `ChatView.tsx` rendering**

```tsx
{items.map((event, idx) => {
  switch (event.type) {
    case 'user':
    case 'agent':
      return <MessageBubble key={idx} message={event} />
    case 'tool':
      return <ToolCallBubble key={idx} message={event} />
    case 'quiz':
      return (
        <QuizCard
          key={idx}
          quiz={event}
          status={event.status as 'pending' | 'answered' | 'skipped'}
          userAnswer={(event.data as QuizEventData)?.user_answer}
          correctAnswer={(event.data as QuizEventData)?.answer}
          analysis={(event.data as QuizEventData)?.analysis}
          onSubmit={() => {}}
          onSkip={() => {}}
        />
      )
  }
})}
```

For `pendingQuiz` rendering:
```tsx
{streamStatus === 'quiz_interrupted' && pendingQuiz && (
  <QuizCard
    quiz={pendingQuiz}
    status="pending"
    onSubmit={answer => submitQuiz('answer', answer)}
    onSkip={() => submitQuiz('skip')}
  />
)}
```

- [ ] **Step 5: Update `StudentChatViewer.tsx`**

Update items type from `ChatItem[]` to `ChatEvent[]`. The rendering switch is the same as ChatView.

- [ ] **Step 6: Verify frontend builds**

```bash
cd frontend && bun run typecheck && bun run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/
git commit -m "refactor: frontend components for ChatEvent"
```

---

## Task 7: E2E Verification

**Files:**
- No file changes - verification only

- [ ] **Step 1: Restart backend**

```bash
pkill -f "uvicorn tutoring.main:app" || true
sleep 1
cd backend && nohup uv run uvicorn tutoring.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn_chat.log 2>&1 &
sleep 8
curl -s http://localhost:8000/health | python3 -m json.tool
```

- [ ] **Step 2: Test - create session + send message**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"teacher1","password":"teacher123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
SESSION=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"free"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session: $SESSION"
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"你好"}' 2>&1 | head -10
```

Expected: `event: text` events followed by `event: done`.

- [ ] **Step 3: Test - History API (DB only, no checkpoint)**

```bash
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('items:', len(d['items']))
print('pending_quiz:', d.get('pending_quiz'))
print('processing:', d.get('processing'))
for i in d['items']:
    print(f\"  {i['type']}: {str(i.get('content', i.get('data', {}).get('stem', '')))[:50]}\")
"
```

Expected: items has user + agent messages, pending_quiz is null, processing is false.

- [ ] **Step 4: Test - quiz flow**

```bash
# Use project mode session for quiz
SESSION2=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"project","project_id":"2c700ce7-3fdc-4672-9813-ba751bdc87a6"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION2/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"出题考考我"}' 2>&1 | grep -E "event:" | head -10
# Check history has pending quiz
curl -s "http://localhost:8000/sessions/$SESSION2/history" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
pq = d.get('pending_quiz')
print('pending_quiz:', 'YES' if pq else 'None')
if pq:
    print('  type:', pq['type'])
    print('  status:', pq['status'])
    print('  topic:', pq['data'].get('topic'))
"
```

Expected: `pending_quiz` is not null, `type='quiz'`, `status='pending'`.

- [ ] **Step 5: Test - is_interrupted uses DB (not checkpoint)**

```bash
# Try sending message to interrupted session
curl -s -X POST "http://localhost:8000/chat/sessions/$SESSION2/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"test"}' 2>&1
```

Expected: 409 `SESSION_INTERRUPTED`.

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: e2e verification fixes"
```

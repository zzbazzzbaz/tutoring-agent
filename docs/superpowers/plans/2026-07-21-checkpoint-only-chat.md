# Checkpoint-Only Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate `chat_event` table, use LangGraph checkpoint as single source of truth for all conversation data, remove `answer`/`analysis` from `present_question` tool.

**Architecture:** Checkpoint stores all messages (HumanMessage, AIMessage, ToolMessage) and interrupt state. History API reads from `agent.aget_state()`. Tools don't touch DB. Background task only streams events, no DB saving.

**Tech Stack:** FastAPI, SQLModel, LangGraph 1.x, PostgreSQL, React 19, Zustand 5

## Global Constraints

- DB columns use `TIMESTAMP(timezone=True)` + `server_default=func.now()`
- No data migration - drop `chat_event` table (user confirmed)
- `present_question` tool: no `answer`/`analysis` params, no DB writes
- History API needs `agent` dependency (reads checkpoint)
- `is_interrupted` reads `state.next` from checkpoint (needs `agent`)
- Backend verify: `uv run python -c "from tutoring.main import app; print('OK')"`
- Frontend verify: `bun run typecheck && bun run build`
- DB: `PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db`

## File Structure

**Backend - modify:**
- `backend/src/tutoring/db/models.py` - Delete ChatEvent model
- `backend/src/tutoring/db/repos.py` - Delete event repos + Pydantic models
- `backend/src/tutoring/db/__init__.py` - Remove event exports
- `backend/src/tutoring/agent/schemas.py` - Remove answer/analysis from PresentQuestionArgs
- `backend/src/tutoring/agent/prompts.py` - Update prompt (remove answer/analysis)
- `backend/src/tutoring/agent/tools.py` - Rewrite present_question (no DB, no answer/analysis)
- `backend/src/tutoring/chat/schemas.py` - New HistoryItemOut, HistoryOut
- `backend/src/tutoring/chat/service.py` - Rewrite build_history, is_interrupted, run_agent_background
- `backend/src/tutoring/chat/sse.py` - Remove DB saves, is_interrupted takes agent
- `backend/src/tutoring/chat/router.py` - History endpoint needs agent dependency
- `backend/tests/conftest.py` - Remove chat_event cleanup

**Frontend - modify:**
- `frontend/src/types/message.ts` - New HistoryItem type
- `frontend/src/types/session.ts` - Update HistoryResponse
- `frontend/src/types/chat.ts` - Simplify
- `frontend/src/api/sessions.ts` - No change
- `frontend/src/api/chat.ts` - No change
- `frontend/src/stores/chat.ts` - Simplify (no DB event creation)
- `frontend/src/features/chat/ChatView.tsx` - Render by item.type
- `frontend/src/features/chat/MessageBubble.tsx` - Accept content + role props
- `frontend/src/features/chat/QuizCard.tsx` - Accept HistoryItem
- `frontend/src/features/chat/ToolCallBubble.tsx` - Accept tool_name + tool_input
- `frontend/src/features/students/StudentChatViewer.tsx` - Update rendering

---

## Task 1: DB - Drop chat_event, Remove Model + Repos

**Files:**
- Modify: `backend/src/tutoring/db/models.py`
- Modify: `backend/src/tutoring/db/repos.py`
- Modify: `backend/src/tutoring/db/__init__.py`

**Interfaces:**
- Produces: Clean models.py (no ChatEvent), clean repos.py (no event repos)

- [ ] **Step 1: Drop chat_event table**

```bash
PGPASSWORD=tutoring123456 psql -h localhost -p 15423 -U tutoring -d tutoring_db -c "DROP TABLE IF EXISTS chat_event CASCADE;"
```

- [ ] **Step 2: Delete ChatEvent model from models.py**

Delete the entire `ChatEvent` class. In the `Session` class, replace:
```python
    events: list["ChatEvent"] = Relationship(back_populates="session", cascade_delete=True)
```
with nothing (remove the line). The Session class should only have:
```python
    project: Project | None = Relationship(back_populates="sessions")
    user: User | None = Relationship(back_populates="sessions")
```

- [ ] **Step 3: Delete event repos + Pydantic models from repos.py**

Delete: `ToolEventData`, `QuizEventData` classes.
Delete: `save_event`, `list_events`, `update_quiz_status`, `has_pending_quiz`, `get_last_user_event` functions.
Delete the `# === ChatEvent ===` section header.

Keep all User, AuthToken, Session, Project repos unchanged.

Update the import at the top:
```python
from tutoring.db.models import AuthToken, Project, Session, User
```
(Remove `ChatEvent` from imports)

- [ ] **Step 4: Update __init__.py**

Remove all ChatEvent-related exports. The file should only export User, AuthToken, Session, Project repos.

- [ ] **Step 5: Verify backend compiles**

```bash
cd backend && uv run python -c "from tutoring.db import repos; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/tutoring/db/
git commit -m "refactor: drop chat_event table, model, and repos"
```

---

## Task 2: Agent - Update PresentQuestionArgs + Prompt + Tool

**Files:**
- Modify: `backend/src/tutoring/agent/schemas.py`
- Modify: `backend/src/tutoring/agent/prompts.py`
- Modify: `backend/src/tutoring/agent/tools.py`

**Interfaces:**
- Produces: `PresentQuestionArgs` without answer/analysis, `present_question` tool with no DB

- [ ] **Step 1: Remove answer/analysis from PresentQuestionArgs**

In `schemas.py`, replace the `PresentQuestionArgs` class:

```python
class PresentQuestionArgs(BaseModel):
    topic: str = Field(description="知识点名称，如 TCP三次握手")
    q_type: Literal["single", "multi", "short"] = Field(description="题型：single=单选 multi=多选 short=简答")
    stem: str = Field(description="题干文本")
    options: list[str] | None = Field(
        None,
        description='选项列表数组，如 ["选项A","选项B","选项C","选项D"]。简答题传 null。'
    )

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
            return [v]
        return None
```

- [ ] **Step 2: Update prompt in prompts.py**

Replace the `_CORE_PRINCIPLES` section about quiz flow. Replace lines containing "出题与评估流程" through "可用工具" with:

```python
出题与评估流程（极其重要）
当学生说"考考我"/"出题"/"测验"/"quiz"等任何表达想做题意图的话时，必须通过调用 present_question 工具出题，禁止自己在文本里写题目和选项然后让学生回答。

完整流程：
1. [可选] 先调 search_knowledge 检索相关知识作为出题素材
2. 在你的推理中设计题目：
   - 考察理解，不考死记硬背
   - 单选题 4 个选项；多选题 4-6 个选项；简答题无选项
3. 调用 present_question(topic, q_type, stem, options)
4. 工具会暂停等待学生答题，学生提交后返回 {question_id, student_answer}
5. 拿到学生答案后，基于你的专业知识自行评估对错
6. 在回复中给学生反馈，继续苏格拉底式追问

只有在学生明确表示不想做题、或你在引导推导过程中需要反问时，才可以在文本中提问。这类反问是引导思考的追问，不是"考题"。

## 可用工具
- search_knowledge(query): 检索课程知识库（含知识图谱），返回相关知识片段
- present_question(topic, q_type, stem, options): 向学生展示一道题并等待作答，返回学生答案
```

- [ ] **Step 3: Rewrite present_question tool in tools.py**

Replace the entire `present_question` function:

```python
    @tool(
        description="向学生展示一道题目并等待作答。调用后会暂停等待学生答题，学生提交后返回其答案。拿到答案后请基于你的专业知识自行评估对错并在回复中给学生反馈。",
        args_schema=PresentQuestionArgs,
    )
    async def present_question(
        topic: str,
        q_type: Literal["single", "multi", "short"],
        stem: str,
        options: list[str] | None,
        config: RunnableConfig,
    ) -> dict:
        from langgraph.types import interrupt
        import uuid as _uuid

        quiz_id = str(_uuid.uuid4())
        student_answer = interrupt(
            {
                "question_id": quiz_id,
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        if student_answer.get("action") == "skip":
            return {"question_id": quiz_id, "action": "skipped"}

        return {"question_id": quiz_id, "student_answer": student_answer.get("answer", "")}
```

Remove the `_db_session` context manager if no other tool uses it. Check `search_knowledge` - it does NOT use `_db_session`. So remove `_db_session` and the `db_session_factory` parameter from `make_tools` if no longer needed.

Check `make_tools` signature: `make_tools(*, rag, db_session_factory)`. If `db_session_factory` is no longer used by any tool, remove it. But check `factory.py` which calls `make_tools(rag=rag, db_session_factory=db_session_factory)` - update both.

Actually, keep `db_session_factory` in `make_tools` for now (future tools may need it). Just remove the `_db_session` usage from `present_question`.

- [ ] **Step 4: Verify backend compiles**

```bash
cd backend && uv run python -c "from tutoring.agent.tools import make_tools; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/tutoring/agent/
git commit -m "refactor: present_question - no DB, no answer/analysis params"
```

---

## Task 3: Backend - Rewrite Schemas + Service

**Files:**
- Modify: `backend/src/tutoring/chat/schemas.py`
- Modify: `backend/src/tutoring/chat/service.py`

**Interfaces:**
- Consumes: `agent.aget_state()` from LangGraph
- Produces: `build_history(agent, session_id)`, `is_interrupted(agent, session_id)`, simplified `run_agent_background`

- [ ] **Step 1: Rewrite schemas.py**

Replace `ChatEventOut` and `HistoryOut` with:

```python
class HistoryItemOut(BaseModel):
    type: str
    content: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    quiz_id: str | None = None
    topic: str | None = None
    q_type: str | None = None
    stem: str | None = None
    options: list[str] | None = None
    status: str | None = None
    user_answer: str | None = None


class HistoryOut(BaseModel):
    items: list[HistoryItemOut]
    pending_quiz: dict | None = None
    processing: bool = False
```

Keep `SessionCreate`, `SessionOut`, `SendMessageRequest` (keep `retry` field for compat), `QuizResumeRequest` unchanged.

- [ ] **Step 2: Rewrite service.py - complete file**

```python
import asyncio
import inspect
import json
import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.prompts import AgentContext
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Session

logger = logging.getLogger(__name__)

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}


def get_running_task(session_id: uuid.UUID) -> asyncio.Task | None:
    task = _running_tasks.get(session_id)
    if task and not task.done():
        return task
    _running_tasks.pop(session_id, None)
    return None


async def get_readable_session(db: AsyncSession, session_id: uuid.UUID, user: CurrentUser) -> Session:
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if user.role == "student" and sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def get_writable_session(db: AsyncSession, session_id: uuid.UUID, user: CurrentUser) -> Session:
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def build_agent_context(db: AsyncSession, sess: Session) -> AgentContext:
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


def _stream_config(session_id: uuid.UUID) -> dict:
    return {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }


async def is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    return bool(state.next)


def session_to_out_dict(sess: Session) -> dict:
    data = {
        "id": sess.id,
        "user_id": sess.user_id,
        "mode": sess.mode,
        "project_id": sess.project_id,
        "title": sess.title,
        "last_active_at": sess.last_active_at,
        "created_at": sess.created_at,
    }
    if sess.project is not None:
        data["project_name"] = sess.project.name
    return data


def _extract_items(messages: list) -> list[dict]:
    items: list[dict] = []
    pending_quiz_indices: list[int] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            if msg.text:
                items.append({"type": "user", "content": msg.text})

        elif isinstance(msg, AIMessage):
            tc = getattr(msg, "tool_calls", None)
            if tc and not inspect.isawaitable(tc):
                try:
                    for call in tc:
                        name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
                        args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                        if name == "present_question":
                            items.append({
                                "type": "quiz",
                                "quiz_id": "",
                                "topic": args.get("topic", ""),
                                "q_type": args.get("q_type", ""),
                                "stem": args.get("stem", ""),
                                "options": args.get("options"),
                                "status": "pending",
                                "user_answer": None,
                            })
                            pending_quiz_indices.append(len(items) - 1)
                        elif name:
                            items.append({
                                "type": "tool_call",
                                "tool_name": name,
                                "tool_input": args,
                            })
                except TypeError:
                    pass

            if msg.text:
                items.append({"type": "agent", "content": msg.text})

        elif isinstance(msg, ToolMessage):
            content_str = msg.text or ""
            try:
                result = json.loads(content_str)
            except (json.JSONDecodeError, TypeError):
                result = {}

            if pending_quiz_indices:
                idx = pending_quiz_indices.pop(0)
                if isinstance(result, dict):
                    if result.get("action") == "skipped":
                        items[idx]["status"] = "skipped"
                    elif "student_answer" in result:
                        items[idx]["status"] = "answered"
                        items[idx]["user_answer"] = result["student_answer"]
                    items[idx]["quiz_id"] = result.get("question_id", "")

    return items


async def build_history(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
) -> dict:
    config = _stream_config(session_id)
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    items = _extract_items(messages)

    pending_quiz = None
    if state.next:
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    if hasattr(intr, "value"):
                        pending_quiz = intr.value
                        break
            if pending_quiz:
                break

    task = get_running_task(session_id)
    processing = bool(task and not task.done())

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}


def _yield_tool_starts(message) -> list[dict]:
    events = []
    tc = getattr(message, "tool_calls", None)
    if tc and not inspect.isawaitable(tc):
        try:
            for call in tc:
                name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
                args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                if name and name != "present_question":
                    events.append({"event": "tool_start", "data": {
                        "tool_name": name, "tool_input": args,
                    }})
        except TypeError:
            pass
    return events


async def run_agent_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config, version="v3", context=context,
        )
        async for message in stream.messages:
            for ev in _yield_tool_starts(message):
                await queue.put(ev)
            async for token in message.text:
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_agent_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)


async def run_resume_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
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
            for ev in _yield_tool_starts(message):
                await queue.put(ev)
            async for token in message.text:
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_resume_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)
```

- [ ] **Step 3: Verify backend compiles**

```bash
cd backend && uv run python -c "from tutoring.chat import service; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/tutoring/chat/schemas.py backend/src/tutoring/chat/service.py
git commit -m "refactor: rewrite build_history + is_interrupted + run_agent_background for checkpoint-only"
```

---

## Task 4: Backend - Update SSE + Router + conftest

**Files:**
- Modify: `backend/src/tutoring/chat/sse.py`
- Modify: `backend/src/tutoring/chat/router.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `service.build_history(agent, session_id)`, `service.is_interrupted(agent, session_id)`
- Produces: Updated SSE endpoints (no DB saves), History endpoint with agent dep

- [ ] **Step 1: Update sse.py - send_message**

In `send_message`, make these changes:

1. Change `is_interrupted` call to pass `agent` instead of `db_session`:
```python
    if await chat_service.is_interrupted(agent, session_id):
```

2. Remove the user message save block (the `if body.retry:` / `else:` block that calls `repos.save_event`). Replace with nothing - user message goes to checkpoint automatically.

3. Keep `touch_session` call (still needed for last_active_at).

4. Keep `get_running_task` check.

5. Keep `build_agent_context` and background task creation.

The `db_session_factory` parameter is still needed for `run_agent_background` signature but the function doesn't use it. Keep passing it.

- [ ] **Step 2: Update sse.py - resume_quiz_endpoint**

Change `is_interrupted` call:
```python
    if not await chat_service.is_interrupted(agent, session_id):
```

- [ ] **Step 3: Update router.py - get_history needs agent dependency**

```python
from langgraph.graph.state import CompiledStateGraph
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db

@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
) -> HistoryOut:
    await chat_service.get_readable_session(db_session, session_id, user)
    result = await chat_service.build_history(agent, session_id)
    return HistoryOut(**result)
```

- [ ] **Step 4: Update conftest.py**

Remove `chat_event` cleanup line:
```python
# Remove this line:
# await conn.execute(text("DELETE FROM chat_event"))
```

Keep `session` cleanup:
```python
        await conn.execute(text("DELETE FROM session"))
```

- [ ] **Step 5: Verify backend compiles and starts**

```bash
cd backend && uv run python -c "from tutoring.main import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/tutoring/chat/sse.py backend/src/tutoring/chat/router.py backend/tests/conftest.py
git commit -m "refactor: SSE no DB saves, History endpoint with agent dep, conftest cleanup"
```

---

## Task 5: Frontend Types + Store

**Files:**
- Modify: `frontend/src/types/message.ts`
- Modify: `frontend/src/types/session.ts`
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/stores/chat.ts`

**Interfaces:**
- Produces: `HistoryItem`, `HistoryResponse`, simplified `useChatStore`

- [ ] **Step 1: Rewrite `frontend/src/types/message.ts`**

```typescript
export interface HistoryItem {
  type: 'user' | 'agent' | 'tool_call' | 'quiz'
  content?: string | null
  tool_name?: string | null
  tool_input?: Record<string, unknown> | null
  quiz_id?: string | null
  topic?: string | null
  q_type?: 'single' | 'multi' | 'short' | null
  stem?: string | null
  options?: string[] | null
  status?: 'pending' | 'answered' | 'skipped' | null
  user_answer?: string | null
}

export interface QuizInterruptData {
  question_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
}
```

- [ ] **Step 2: Rewrite `frontend/src/types/session.ts`**

```typescript
import type { HistoryItem, QuizInterruptData } from './message'

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
  items: HistoryItem[]
  pending_quiz: QuizInterruptData | null
  processing: boolean
}
```

- [ ] **Step 3: Rewrite `frontend/src/types/chat.ts`**

```typescript
import type { HistoryItem } from './message'

export type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

export type ChatItem = HistoryItem
```

- [ ] **Step 4: Rewrite `frontend/src/stores/chat.ts`**

Key changes from current store:
- `items` type: `HistoryItem[]`
- `pendingQuiz` type: `QuizInterruptData | null`
- `sendMessage`: user msg is `{type: 'user', content}`, agent msg is `{type: 'agent', content}`, tool is `{type: 'tool_call', ...}`
- `done` handler: create agent item from streamingContent
- `tool_start` handler: create tool_call item
- `submitQuiz` done handler: create quiz item with status + user_answer
- `selectSession`: uses `history.items` and `history.pending_quiz`
- `recoverFromHistory`: same structure, `history.pending_quiz` is `QuizInterruptData`

```typescript
import { create } from 'zustand'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { streamMessage, resumeQuiz } from '@/api/chat'
import { createSelectors } from '@/lib/utils'
import type { SessionOut, HistoryResponse } from '@/types/session'
import type { HistoryItem, QuizInterruptData } from '@/types/message'
import type { StreamStatus } from '@/types/chat'

interface ChatState {
  sessions: SessionOut[]
  currentSession: SessionOut | null
  items: HistoryItem[]
  streamStatus: StreamStatus
  pendingQuiz: QuizInterruptData | null
  streamingContent: string
  lastError: { message: string; code: string } | null
  currentAbort: AbortController | null
  loadingSession: boolean
  loadingSessions: boolean

  loadSessions: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  submitQuiz: (action: 'answer' | 'skip', answer?: string) => Promise<void>
  retryLastMessage: () => Promise<void>
  recoverFromHistory: () => Promise<void>
  resetStream: () => void
  clearCurrent: () => void
}

function makeUserItem(content: string): HistoryItem {
  return { type: 'user', content }
}

function makeAgentItem(content: string): HistoryItem {
  return { type: 'agent', content }
}

function makeToolItem(toolName: string, toolInput: Record<string, unknown>): HistoryItem {
  return { type: 'tool_call', tool_name: toolName, tool_input: toolInput }
}

const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSession: null,
  items: [],
  streamStatus: 'idle',
  pendingQuiz: null,
  streamingContent: '',
  lastError: null,
  currentAbort: null,
  loadingSession: false,
  loadingSessions: false,

  loadSessions: async () => {
    set({ loadingSessions: true })
    try {
      const sessions = await sessionsApi.list({ limit: 50 })
      set({ sessions })
    } finally {
      set({ loadingSessions: false })
    }
  },

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
        streamStatus: history.pending_quiz ? 'quiz_interrupted' : (history.processing ? 'streaming' : 'idle'),
      })
    } finally {
      set({ loadingSession: false })
    }
  },

  sendMessage: async content => {
    const { currentSession } = get()
    if (!currentSession) return
    if (get().streamStatus === 'streaming' || get().streamStatus === 'quiz_interrupted') return

    set(state => ({
      items: [...state.items, makeUserItem(content)],
      streamStatus: 'streaming',
      streamingContent: '',
      lastError: null,
    }))

    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, content, ac.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
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
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'error', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } })
        toast.error('连接中断')
      }
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
  },

  submitQuiz: async (action, answer) => {
    const { currentSession, pendingQuiz, currentAbort } = get()
    if (!currentSession || !pendingQuiz) return

    set({ streamStatus: 'streaming', streamingContent: '' })

    try {
      for await (const ev of resumeQuiz(currentSession.id, action, answer ?? null, currentAbort?.signal)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              const quizItem: HistoryItem = {
                type: 'quiz',
                quiz_id: pendingQuiz.question_id,
                topic: pendingQuiz.topic,
                q_type: pendingQuiz.q_type,
                stem: pendingQuiz.stem,
                options: pendingQuiz.options,
                status: action === 'skip' ? 'skipped' : 'answered',
                user_answer: action === 'skip' ? null : (answer ?? null),
              }
              const agentItem = makeAgentItem(get().streamingContent)
              set(state => ({ items: [...state.items, quizItem, agentItem], pendingQuiz: null, streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
              } else {
                set({ streamingContent: '' })
              }
            }
            break
          case 'error':
            set({ streamStatus: 'quiz_interrupted', lastError: ev.data })
            toast.error(ev.data.message)
            break
        }
      }
      if (get().streamStatus === 'streaming') {
        set({ streamStatus: 'quiz_interrupted', lastError: { message: '连接中断，请重新答题', code: 'STREAM_CLOSED' } })
        toast.error('连接中断，请重新答题')
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

  retryLastMessage: async () => {
    const { currentSession, items } = get()
    if (!currentSession) return
    const lastUserMsg = [...items].reverse().find(e => e.type === 'user')
    if (!lastUserMsg?.content) return

    set({ streamStatus: 'streaming', streamingContent: '', lastError: null })
    const ac = new AbortController()
    set({ currentAbort: ac })

    try {
      for await (const ev of streamMessage(currentSession.id, lastUserMsg.content, ac.signal, true)) {
        switch (ev.event) {
          case 'text':
            set(state => ({ streamingContent: state.streamingContent + ev.data.content }))
            break
          case 'tool_start':
            set(state => ({ items: [...state.items, makeToolItem(ev.data.tool_name, ev.data.tool_input)] }))
            break
          case 'quiz_interrupt':
            set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' })
            break
          case 'done':
            if (get().streamStatus === 'streaming') {
              set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamStatus: 'idle', streamingContent: '' }))
            } else if (get().streamStatus === 'quiz_interrupted') {
              if (get().streamingContent) {
                set(state => ({ items: [...state.items, makeAgentItem(get().streamingContent)], streamingContent: '' }))
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

  recoverFromHistory: async () => {
    const { currentSession } = get()
    if (!currentSession) return
    try {
      const history: HistoryResponse = await sessionsApi.getHistory(currentSession.id)
      if (history.pending_quiz) {
        set({ items: history.items, pendingQuiz: history.pending_quiz, streamStatus: 'quiz_interrupted', streamingContent: '' })
      } else if (history.processing) {
        set({ items: history.items, streamStatus: 'streaming' })
        setTimeout(() => get().recoverFromHistory(), 3000)
      } else {
        const lastAgent = [...history.items].reverse().find(e => e.type === 'agent')
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

  resetStream: () => {
    const ac = get().currentAbort
    if (ac) ac.abort()
    set({
      streamStatus: 'idle',
      streamingContent: '',
      pendingQuiz: null,
      lastError: null,
      currentAbort: null,
    })
  },

  clearCurrent: () => {
    get().resetStream()
    set({ currentSession: null, items: [], loadingSession: false })
  },
}))

export const useChat = createSelectors(useChatStore)
export { useChatStore }
```

- [ ] **Step 5: Verify frontend compiles**

```bash
cd frontend && bun run typecheck
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/ frontend/src/stores/
git commit -m "refactor: frontend types + store for checkpoint-only HistoryItem"
```

---

## Task 6: Frontend Components

**Files:**
- Modify: `frontend/src/features/chat/MessageBubble.tsx`
- Modify: `frontend/src/features/chat/QuizCard.tsx`
- Modify: `frontend/src/features/chat/ToolCallBubble.tsx`
- Modify: `frontend/src/features/chat/ChatView.tsx`
- Modify: `frontend/src/features/students/StudentChatViewer.tsx`

**Interfaces:**
- Consumes: `HistoryItem` type from Task 5

- [ ] **Step 1: Update MessageBubble.tsx**

Change props to accept `HistoryItem`:

```typescript
import type { HistoryItem } from '@/types/message'

export default function MessageBubble({ message }: { message: HistoryItem }) {
```

Change `isUser` check from `message.type === 'user'` (already correct). Change `message.content` to `message.content || ''`.

- [ ] **Step 2: Update ToolCallBubble.tsx**

```tsx
import { Search } from 'lucide-react'
import type { HistoryItem } from '@/types/message'

export default function ToolCallBubble({ message }: { message: HistoryItem }) {
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

- [ ] **Step 3: Update QuizCard.tsx**

Change props to accept `HistoryItem`:

```typescript
import type { HistoryItem } from '@/types/message'

interface QuizCardProps {
  quiz: HistoryItem
  status: 'pending' | 'answered' | 'skipped'
  userAnswer?: string | null
  onSubmit: (answer: string) => void
  onSkip: () => void
}
```

Extract quiz fields directly from `quiz` (no more `quiz.data` cast):
```typescript
const qType = quiz.q_type || 'single'
const options = quiz.options ?? []
const stem = quiz.stem || ''
const topic = quiz.topic || ''
const questionId = quiz.quiz_id || ''
```

Keep the rest of the component the same (no correct/wrong, no analysis - already simplified in previous task).

- [ ] **Step 4: Update ChatView.tsx**

```tsx
import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import QuizCard from './QuizCard'
import ToolCallBubble from './ToolCallBubble'
import MarkdownRenderer from '@/features/shared/MarkdownRenderer'

export default function ChatView() {
  const items = useChatStore(s => s.items)
  const streamStatus = useChatStore(s => s.streamStatus)
  const streamingContent = useChatStore(s => s.streamingContent)
  const pendingQuiz = useChatStore(s => s.pendingQuiz)
  const lastError = useChatStore(s => s.lastError)
  const sendMessage = useChatStore(s => s.sendMessage)
  const submitQuiz = useChatStore(s => s.submitQuiz)
  const retryLastMessage = useChatStore(s => s.retryLastMessage)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, streamingContent, pendingQuiz])

  const inputDisabled = streamStatus === 'streaming' || streamStatus === 'quiz_interrupted'
  const showRetry = streamStatus === 'error' && lastError?.code === 'RETRYABLE'

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {items.map((item, idx) => {
          switch (item.type) {
            case 'user':
            case 'agent':
              return <MessageBubble key={idx} message={item} />
            case 'tool_call':
              return <ToolCallBubble key={idx} message={item} />
            case 'quiz':
              if (item.status === 'pending') return null
              return (
                <QuizCard
                  key={idx}
                  quiz={item}
                  status={item.status as 'pending' | 'answered' | 'skipped'}
                  userAnswer={item.user_answer}
                  onSubmit={() => {}}
                  onSkip={() => {}}
                />
              )
          }
        })}
        {streamStatus === 'streaming' && streamingContent && (
          <div className="flex gap-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
              <span className="text-xs">AI</span>
            </div>
            <div className="flex-1 text-sm">
              <MarkdownRenderer content={streamingContent} />
            </div>
          </div>
        )}
        {streamStatus === 'quiz_interrupted' && pendingQuiz && (
          <QuizCard
            quiz={{
              type: 'quiz',
              quiz_id: pendingQuiz.question_id,
              topic: pendingQuiz.topic,
              q_type: pendingQuiz.q_type,
              stem: pendingQuiz.stem,
              options: pendingQuiz.options,
              status: 'pending',
              user_answer: null,
            }}
            status="pending"
            onSubmit={answer => submitQuiz('answer', answer)}
            onSkip={() => submitQuiz('skip')}
          />
        )}
        {showRetry && (
          <div className="flex justify-center">
            <button
              onClick={() => retryLastMessage()}
              className="rounded-lg border bg-muted/50 px-4 py-2 text-sm hover:bg-muted"
            >
              重试
            </button>
          </div>
        )}
      </div>
      <ChatInput
        onSend={sendMessage}
        disabled={inputDisabled}
        hint={streamStatus === 'quiz_interrupted' ? '请先回答上方题目' : undefined}
      />
    </div>
  )
}
```

- [ ] **Step 5: Update StudentChatViewer.tsx**

Update the rendering to use the same switch pattern:

```tsx
import type { HistoryItem } from '@/types/message'
```

Change `items` state type to `HistoryItem[]`. Update rendering:
```tsx
{items.map((event, idx) => {
  switch (event.type) {
    case 'user':
    case 'agent':
      return <MessageBubble key={idx} message={event} />
    case 'tool_call':
      return <ToolCallBubble key={idx} message={event} />
    case 'quiz':
      return (
        <QuizCard
          key={idx}
          quiz={event}
          status={event.status as 'pending' | 'answered' | 'skipped'}
          userAnswer={event.user_answer}
          onSubmit={() => {}}
          onSkip={() => {}}
        />
      )
  }
})}
```

- [ ] **Step 6: Verify frontend builds**

```bash
cd frontend && bun run typecheck && bun run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/
git commit -m "refactor: frontend components for HistoryItem type"
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
curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])"
```

- [ ] **Step 2: Test - create session + send message**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"teacher1","password":"teacher123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
SESSION=$(curl -s -X POST "http://localhost:8000/sessions" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"mode":"free"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session: $SESSION"
curl -sN -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"你好"}' 2>&1 | grep -E "event:" | head -5
```

Expected: `event: text` events followed by `event: done`.

- [ ] **Step 3: Test - History API (from checkpoint)**

```bash
sleep 3
curl -s "http://localhost:8000/sessions/$SESSION/history" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('items:', len(d['items']))
print('pending_quiz:', d.get('pending_quiz'))
print('processing:', d.get('processing'))
for i in d['items']:
    print(f'  {i[\"type\"]}: {str(i.get(\"content\", i.get(\"tool_name\", i.get(\"topic\", \"\"))))[:50]}')
"
```

Expected: items has user + agent, pending_quiz is null, processing is false.

- [ ] **Step 4: Test - is_interrupted from checkpoint**

```bash
curl -s -X POST "http://localhost:8000/chat/sessions/$SESSION/messages" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"content":"test"}' 2>&1 | head -5
```

If agent is running, expect 409 SESSION_PROCESSING. If not, expect normal SSE.

- [ ] **Step 5: Test - frontend build**

```bash
cd frontend && bun run build 2>&1 | tail -3
```

Expected: Build successful.

- [ ] **Step 6: Final commit if fixes needed**

```bash
git add -A
git commit -m "fix: e2e verification fixes"
```

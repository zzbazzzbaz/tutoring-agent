import asyncio
import inspect
import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, ToolMessage
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


async def is_interrupted(db: AsyncSession, session_id: uuid.UUID) -> bool:
    return await repos.has_pending_quiz(db, session_id)


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


def _stream_config(session_id: uuid.UUID) -> dict:
    return {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }


def _event_to_dict(e) -> dict:
    data = e.data
    if e.type == "quiz" and data:
        data = {k: v for k, v in data.items() if k not in ("answer", "analysis")}
    return {
        "id": str(e.id),
        "session_id": str(e.session_id),
        "type": e.type,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "content": e.content,
        "data": data,
        "status": e.status,
        "answered_at": e.answered_at.isoformat() if e.answered_at else None,
    }


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


async def _process_stream(stream, queue: asyncio.Queue) -> tuple[str, list[tuple[str, dict | None, str]]]:
    """Accumulate text + tool calls from stream. Returns (full_text, completed_tools)."""
    full_text = ""
    pending_tools: list[tuple[str, dict | None]] = []
    completed_tools: list[tuple[str, dict | None, str]] = []

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

    return full_text, completed_tools


async def _save_results(
    db_session_factory, session_id, full_text, completed_tools,
) -> None:
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


async def run_agent_background(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    queue: asyncio.Queue,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config, version="v3", context=context,
        )
        full_text, completed_tools = await _process_stream(stream, queue)

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        await _save_results(db_session_factory, session_id, full_text, completed_tools)
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
    db_session_factory: async_sessionmaker[AsyncSession],
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
        full_text, completed_tools = await _process_stream(stream, queue)

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        await _save_results(db_session_factory, session_id, full_text, completed_tools)
        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("run_resume_background failed")
        await queue.put({"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}})
    finally:
        _running_tasks.pop(session_id, None)

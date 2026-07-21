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

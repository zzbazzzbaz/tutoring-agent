import asyncio
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


async def is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    config = {"configurable": {"thread_id": str(session_id)}}
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


def _stream_config(session_id: uuid.UUID) -> dict:
    return {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }


def _yield_tool_starts(message) -> list[dict]:
    events = []
    tc = getattr(message, "tool_calls", None)
    if tc is None:
        return events
    import inspect
    if inspect.isawaitable(tc):
        return events
    try:
        for call in tc:
            name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
            if name and name != "present_question":
                args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
                events.append({"event": "tool_start", "data": {
                    "tool_name": name,
                    "tool_input": args,
                }})
    except TypeError:
        pass
    return events


async def stream_chat_events(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[dict]:
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            for ev in _yield_tool_starts(message):
                yield ev
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


async def resume_quiz_events(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    db_session: AsyncSession,
    context: AgentContext,
) -> AsyncIterator[dict]:
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
            for ev in _yield_tool_starts(message):
                yield ev
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


async def save_final_agent_message(
    agent: CompiledStateGraph,
    config: dict,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if not messages:
        return
    text = messages[-1].text
    if text:
        existing = await repos.list_messages(db_session, session_id)
        if not any(m.role == "agent" and m.content == text for m in existing):
            await repos.save_message(
                db_session, session_id=session_id, role="agent", content=text
            )


async def save_tool_messages(
    agent: CompiledStateGraph,
    config: dict,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    existing = await repos.list_messages(db_session, session_id)
    existing_tool_ids = {m.tool_name for m in existing if m.role == "tool"}

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tc_id = msg.tool_call_id or msg.name or ""
            if tc_id not in existing_tool_ids:
                await repos.save_tool_message(
                    db_session, session_id=session_id,
                    tool_name=msg.name or "unknown",
                    tool_input=None,
                    tool_output=msg.text,
                )
                existing_tool_ids.add(tc_id)


async def sync_checkpoint_to_db(
    agent: CompiledStateGraph,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
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
            elif isinstance(msg, HumanMessage):
                await repos.save_message(db_session, session_id=session_id, role="user", content=text)
                db_contents.add(text)


async def build_history(
    agent: CompiledStateGraph,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> dict:
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
        async for message in stream.messages:
            for ev in _yield_tool_starts(message):
                await queue.put(ev)
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
        async for message in stream.messages:
            for ev in _yield_tool_starts(message):
                await queue.put(ev)
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

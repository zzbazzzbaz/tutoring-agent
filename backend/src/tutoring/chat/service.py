import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.agent.prompts import AgentContext
from tutoring.core.config import settings
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Project, Session

logger = logging.getLogger(__name__)


async def get_owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """存在且归属该用户，否则抛 404/403。"""
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if sess.user_id != user_id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def get_active_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """get_owned_session + 状态 active（chat 流式端点用）。"""
    sess = await get_owned_session(db, session_id, user_id)
    if sess.status != "active":
        raise AppError(409, "SESSION_ENDED", "Session is ended")
    return sess


async def build_agent_context(db: AsyncSession, sess: Session) -> AgentContext:
    """根据 session 模式构建 AgentContext；project 模式查项目信息。"""
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
    """检查 LangGraph state 是否处于 interrupt 待恢复状态。"""
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
        "status": sess.status,
        "last_active_at": sess.last_active_at,
        "created_at": sess.created_at,
    }
    if sess.project is not None:
        data["project_name"] = sess.project.name
    return data


# ---------------------------------------------------------------------------
# 流式编排（协议无关）：输出事件 dict，由 sse.py 格式化为 SSE 帧
# ---------------------------------------------------------------------------

# 事件 schema：
#   {"event": "text",           "data": {"content": "<token>"}}
#   {"event": "quiz_interrupt", "data": {<interrupt.value>}}
#   {"event": "done",           "data": {}}
#   {"event": "error",          "data": {"message": "...", "code": "..."}}


def _stream_config(session_id: uuid.UUID) -> dict:
    """LangGraph stream 配置：thread_id 绑定 session，递归限 15。"""
    return {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }


async def stream_chat_events(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[dict]:
    """首次发送消息 -> 流式事件（协议无关）。

    runtime context 不进 checkpoint，每次调用必须显式传入，
    否则 main_agent_system_prompt 中间件读 context 会拿到 None。
    """
    config = _stream_config(session_id)
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            async for token in message.text:
                yield {"event": "text", "data": {"content": token}}

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield {"event": "quiz_interrupt", "data": it.value}
            yield {"event": "done", "data": {}}
            return

        await save_final_agent_message(agent, config, db_session, session_id)
        yield {"event": "done", "data": {}}
    except Exception as e:
        logger.exception("stream_chat_events 失败")
        yield {"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}}


async def resume_quiz_events(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    db_session: AsyncSession,
    context: AgentContext,
) -> AsyncIterator[dict]:
    """提交答题 -> 流式事件（协议无关）。

    resume 时不会有 quiz_interrupt（除非连续出题）；其余事件类型同 stream_chat_events。
    """
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
            async for token in message.text:
                yield {"event": "text", "data": {"content": token}}

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield {"event": "quiz_interrupt", "data": it.value}
            yield {"event": "done", "data": {}}
            return

        await save_final_agent_message(agent, config, db_session, session_id)
        yield {"event": "done", "data": {}}
    except Exception as e:
        logger.exception("resume_quiz_events 失败")
        yield {"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}}


async def save_final_agent_message(
    agent: CompiledStateGraph,
    config: dict,
    db_session: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """从 LangGraph state 取最终 AIMessage，持久化到 Message 表。"""
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if not messages:
        return
    text = messages[-1].text
    if text:
        await repos.save_message(
            db_session, session_id=session_id, role="agent", content=text
        )

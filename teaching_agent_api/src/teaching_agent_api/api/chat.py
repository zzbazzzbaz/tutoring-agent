"""Chat 端点，SSE 流式响应。"""
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.agent.runtime import resume_quiz, stream_chat
from teaching_agent_api.config import settings
from teaching_agent_api.deps import get_agent, get_db, get_user_id
from teaching_agent_api.schemas.chat import QuizResumeRequest, SendMessageRequest

router = APIRouter(prefix="/chat", tags=["chat"])


async def _validate_session_for_chat(
    db_session: AsyncSession, session_id: uuid.UUID, user_id: str
):
    """通用校验：session 存在、归属用户、状态为 active。"""
    sess = await db.get_session(db_session, session_id)
    if not sess:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found",
                }
            },
        )
    if sess.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Session does not belong to user",
                }
            },
        )
    if sess.status != "active":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "SESSION_ENDED",
                    "message": "Session is ended",
                }
            },
        )
    return sess


async def _build_agent_context(sess, db_session: AsyncSession) -> AgentContext:
    """根据 session 模式构建 AgentContext；project 模式查项目信息。"""
    if sess.mode == "project" and sess.project_id:
        proj = await db.get_project(db_session, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


async def _is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    """检查 LangGraph state 是否处于 interrupt 待恢复状态。"""
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await agent.aget_state(config)
    return bool(state.next)  # 非空 next 表示暂停在 interrupt


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """发送消息，SSE 流式返回 agent 回复（event: text|quiz_interrupt|done|error）。"""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)

    # 若处于 interrupt 状态，不允许发新消息（需先 resume）
    if await _is_interrupted(agent, session_id):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "SESSION_INTERRUPTED",
                    "message": "Session is paused at a quiz; call /quiz/resume first",
                }
            },
        )

    # 落库用户消息
    await db.save_message(
        db_session, session_id=session_id, role="user", content=body.content
    )
    await db.touch_session(db_session, session_id)

    # 构建 AgentContext
    ctx = await _build_agent_context(sess, db_session)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in stream_chat(
                agent, session_id, body.content, ctx, db_session
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
    session_id: uuid.UUID,
    body: QuizResumeRequest,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """提交答题（answer/skip），SSE 流式返回 agent 续接回复。"""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)

    # 必须处于 interrupt 状态才能 resume
    if not await _is_interrupted(agent, session_id):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "SESSION_NOT_INTERRUPTED",
                    "message": "Session is not paused; no quiz to resume",
                }
            },
        )

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in resume_quiz(
                agent, session_id, body.action, body.answer, db_session
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

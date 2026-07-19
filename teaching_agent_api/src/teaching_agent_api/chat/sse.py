"""Chat SSE 端点：send_message + quiz resume。

流式编排逻辑位于 agent.runtime；本模块只做：
- 会话校验（service）
- interrupt 状态检查（service）
- 消息落库 + touch_session
- AgentContext 组装（service）
- 委托 runtime 生成 SSE 帧
"""
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.agent.runtime import resume_quiz, stream_chat
from teaching_agent_api.chat import service as chat_service
from teaching_agent_api.chat.schemas import QuizResumeRequest, SendMessageRequest
from teaching_agent_api.core.deps import CurrentUser, get_agent, get_current_user, get_db
from teaching_agent_api.core.errors import AppError
from teaching_agent_api.db import repos

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """发送消息，SSE 流式返回 agent 回复（event: text|quiz_interrupt|done|error）。"""
    sess = await chat_service.get_active_session(db_session, session_id, user.id)

    # 若处于 interrupt 状态，不允许发新消息（需先 resume）
    if await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_INTERRUPTED",
            "Session is paused at a quiz; call /quiz/resume first",
        )

    # 落库用户消息
    await repos.save_message(
        db_session, session_id=session_id, role="user", content=body.content
    )
    await repos.touch_session(db_session, session_id)

    # 构建 AgentContext
    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in stream_chat(
                agent, session_id, body.content, ctx, db_session
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await repos.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
    session_id: uuid.UUID,
    body: QuizResumeRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """提交答题（answer/skip），SSE 流式返回 agent 续接回复。"""
    sess = await chat_service.get_active_session(db_session, session_id, user.id)

    # 必须处于 interrupt 状态才能 resume
    if not await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_NOT_INTERRUPTED",
            "Session is not paused; no quiz to resume",
        )

    # runtime context 不进 checkpoint，resume 也需重建传入
    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in resume_quiz(
                agent, session_id, body.action, body.answer, db_session, ctx
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await repos.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

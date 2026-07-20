"""Chat SSE 端点：send_message + quiz resume。

流式编排逻辑在 chat/service.py（协议无关，输出事件 dict）。
本模块只负责 HTTP 端点 + SSE 格式化（dict -> SSE 帧）。
"""
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.chat import service as chat_service
from tutoring.chat.schemas import QuizResumeRequest, SendMessageRequest
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    """格式化 SSE 帧。JSON 不转义非 ASCII（中文）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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

    if await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_INTERRUPTED",
            "Session is paused at a quiz; call /quiz/resume first",
        )

    await repos.save_message(
        db_session, session_id=session_id, role="user", content=body.content
    )
    await repos.touch_session(db_session, session_id)

    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for event in chat_service.stream_chat_events(
                agent, session_id, body.content, ctx, db_session
            ):
                yield _sse(event["event"], event["data"]).encode("utf-8")
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

    if not await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_NOT_INTERRUPTED",
            "Session is not paused; no quiz to resume",
        )

    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for event in chat_service.resume_quiz_events(
                agent, session_id, body.action, body.answer, db_session, ctx
            ):
                yield _sse(event["event"], event["data"]).encode("utf-8")
        finally:
            await repos.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

"""Chat SSE 端点：send_message + quiz resume。

Agent 在后台 asyncio.Task 中执行，SSE 只消费 asyncio.Queue。
客户端断开不影响 agent 继续运行。
"""
import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.chat import service as chat_service
from tutoring.chat.schemas import QuizResumeRequest, SendMessageRequest
from tutoring.core.deps import (
    CurrentUser,
    get_agent,
    get_current_user,
    get_db,
    get_db_session_factory,
)
from tutoring.core.errors import AppError
from tutoring.db import repos

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _raw_stream(queue: asyncio.Queue) -> AsyncIterator[bytes]:
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
        pass


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
    db_session_factory: async_sessionmaker[AsyncSession] = Depends(get_db_session_factory),
):
    """发送消息，SSE 流式返回 agent 回复。Agent 在后台运行，SSE 断开不影响。"""
    sess = await chat_service.get_writable_session(db_session, session_id, user)

    if chat_service.get_running_task(session_id):
        raise AppError(
            409, "SESSION_PROCESSING",
            "Agent is already running for this session",
        )

    if await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_INTERRUPTED",
            "Session is paused at a quiz; call /quiz/resume first",
        )

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

    ctx = await chat_service.build_agent_context(db_session, sess)

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        chat_service.run_agent_background(
            agent, session_id, body.content, ctx, queue, db_session_factory,
        )
    )
    chat_service._running_tasks[session_id] = task

    return StreamingResponse(
        _raw_stream(queue),
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
    db_session_factory: async_sessionmaker[AsyncSession] = Depends(get_db_session_factory),
):
    """提交答题（answer/skip），SSE 流式返回 agent 续接回复。"""
    sess = await chat_service.get_writable_session(db_session, session_id, user)

    if chat_service.get_running_task(session_id):
        raise AppError(
            409, "SESSION_PROCESSING",
            "Agent is already running for this session",
        )

    if not await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_NOT_INTERRUPTED",
            "Session is not paused; no quiz to resume",
        )

    ctx = await chat_service.build_agent_context(db_session, sess)

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        chat_service.run_resume_background(
            agent, session_id, body.action, body.answer, ctx, queue, db_session_factory,
        )
    )
    chat_service._running_tasks[session_id] = task

    return StreamingResponse(
        _raw_stream(queue),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

"""Chat SSE: send_message + quiz resume.

Agent runs in background asyncio.Task, SSE consumes from asyncio.Queue.
Client disconnect doesn't cancel the agent.
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
    sess = await chat_service.get_writable_session(db_session, session_id, user)

    if chat_service.get_running_task(session_id):
        raise AppError(409, "SESSION_PROCESSING", "Agent is already running for this session")

    if await chat_service.is_interrupted(db_session, session_id):
        raise AppError(409, "SESSION_INTERRUPTED", "Session is paused at a quiz; call /quiz/resume first")

    if body.retry:
        existing = await repos.list_events(db_session, session_id)
        already_saved = any(e.type == "user" and e.content == body.content for e in existing)
        if not already_saved:
            await repos.save_event(db_session, session_id=session_id, type="user", content=body.content)
    else:
        await repos.save_event(db_session, session_id=session_id, type="user", content=body.content)
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
    sess = await chat_service.get_writable_session(db_session, session_id, user)

    if chat_service.get_running_task(session_id):
        raise AppError(409, "SESSION_PROCESSING", "Agent is already running for this session")

    if not await chat_service.is_interrupted(db_session, session_id):
        raise AppError(409, "SESSION_NOT_INTERRUPTED", "Session is not paused; no quiz to resume")

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

"""chat 模块的 HTTP 入口：同步 REST（/sessions）+ 流式 SSE（/chat/sessions）。

- router：会话增删查改 + 历史重建，同步 JSON 响应。
- sse_router：发消息 / 恢复 quiz，SSE 流式响应。流式入口在后台任务里跑 agent，
  事件通过 asyncio.Queue 推给 SSE 生成器；详见 streaming.py。

sse 层只调 chat 子模块（tasks / sessions / streaming），不直接碰 repos 或
_running_tasks，遵守 AGENTS.md 的分层规则。
"""
import asyncio
import json
from functools import partial
from typing import AsyncIterator, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.agent.prompts import AgentContext
from tutoring.chat import history as chat_history
from tutoring.chat import sessions as chat_sessions
from tutoring.chat import streaming as chat_streaming
from tutoring.chat import tasks as chat_tasks
from tutoring.chat.schemas import (
    HistoryOut,
    QuizResumeRequest,
    SendMessageRequest,
    SessionCreate,
    SessionOut,
)
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.projects import service as project_service

# === 同步 REST：/sessions ===

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
        body: SessionCreate,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    project_obj = None
    if body.mode == "project":
        project_obj = await project_service.get_published_project(db_session, body.project_id)
    sess = await repos.create_session(
        db_session, mode=body.mode, user_id=user.id, project_id=body.project_id
    )
    sess.project = project_obj
    return SessionOut.model_validate(chat_sessions.session_to_out_dict(sess))


@router.get("", response_model=list[SessionOut])
async def list_sessions(
        mode: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    sessions = await repos.list_sessions(
        db_session, user_id=user.id, mode=mode, limit=limit, offset=offset,
    )
    return [SessionOut.model_validate(chat_sessions.session_to_out_dict(s)) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
        session_id: UUID,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    sess = await chat_sessions.get_readable_session(db_session, session_id, user)
    return SessionOut.model_validate(chat_sessions.session_to_out_dict(sess))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
        session_id: UUID,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> None:
    await chat_sessions.get_writable_session(db_session, session_id, user)
    await repos.delete_session(db_session, session_id)


@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
        session_id: UUID,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> HistoryOut:
    await chat_sessions.get_readable_session(db_session, session_id, user)
    result = await chat_history.build_history(str(session_id))
    return HistoryOut(**result)


# === 流式 SSE：/chat/sessions ===

sse_router = APIRouter(prefix="/chat", tags=["chat"])

# 流式入口的统一形态：(ctx, queue) -> coroutine
StreamingEntry = Callable[[AgentContext, asyncio.Queue], Awaitable[None]]


def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _raw_stream(queue: asyncio.Queue) -> AsyncIterator[bytes]:
    """从 queue 取事件转成 SSE 字节流。

    15s 无事件发心跳保活；遇到 done / error 事件收尾退出。
    """
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
        except asyncio.TimeoutError:
            yield b": heartbeat\n\n"
            continue
        yield _sse(event["event"], event["data"]).encode("utf-8")
        if event["event"] in ("done", "error"):
            return


async def _stream_response(
        db_session: AsyncSession,
        sess,
        session_id: UUID,
        run_entry: StreamingEntry,
) -> StreamingResponse:
    agent_context = await chat_sessions.build_agent_context(db_session, sess)
    queue: asyncio.Queue = asyncio.Queue()
    chat_tasks.register(  # 注册任务 # todo 存在多进程下并发安全问题
        session_id=session_id,
        task=asyncio.create_task(run_entry(agent_context, queue)) # run_entry() 创建协程;asyncio.create_task() 执行协程
    )
    return StreamingResponse(
        _raw_stream(queue),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@sse_router.post("/sessions/{session_id}/messages")
async def send_message(
        session_id: UUID,
        body: SendMessageRequest,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
        agent: CompiledStateGraph = Depends(get_agent),
) -> StreamingResponse:
    """发一条新消息并流式回传 agent 响应。"""
    sess = await chat_sessions.get_writable_session(db_session, session_id, user)

    if chat_tasks.get(session_id):
        raise AppError(409, "SESSION_PROCESSING", "Agent is already running for this session")
    if await chat_streaming.is_interrupted(agent, session_id):
        raise AppError(409, "SESSION_INTERRUPTED", "Session is paused at a quiz; call /quiz/resume first")

    await chat_sessions.touch_session(db_session, session_id)

    return await _stream_response(
        db_session, sess, session_id,
        partial(chat_streaming.stream_message, agent, session_id, body.content),
    )


@sse_router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
        session_id: UUID,
        body: QuizResumeRequest,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
        agent: CompiledStateGraph = Depends(get_agent),
) -> StreamingResponse:
    """恢复一个被 quiz interrupt 中断的会话"""
    sess = await chat_sessions.get_writable_session(db_session, session_id, user)

    if chat_tasks.get(session_id):  # 并发互斥，确保没有agent在跑这个任务
        raise AppError(409, "SESSION_PROCESSING", "Agent is already running for this session")
    if not await chat_streaming.is_interrupted(agent, session_id):  # 确保是interrupt状态
        raise AppError(409, "SESSION_NOT_INTERRUPTED", "Session is not paused; no quiz to resume")

    return await _stream_response(
        db_session, sess, session_id,
        partial(chat_streaming.stream_resume, agent, session_id, body.action, body.answer),
    )

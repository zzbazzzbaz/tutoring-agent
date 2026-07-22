"""伪装 LangGraph Server 协议端点，前端用 @langchain/langgraph-sdk 直接打。

- GET  /threads/{thread_id}/state       鉴权后透传 Server state
- POST /threads/{thread_id}/runs/stream  鉴权 + 注入 context/并发参数 -> 透传 SSE
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.chat import server_client
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.sessions import service as session_service

router = APIRouter(tags=["chat"])

_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


@router.get("/threads/{thread_id}/state")
async def get_state(
        thread_id: UUID,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> dict:
    """透传 Server 的 thread state（messages + interrupts + next）。"""
    await session_service.get_readable_session(db_session, thread_id, user)
    return await server_client.get_state(str(thread_id))


@router.post("/threads/{thread_id}/runs/stream")
async def runs_stream(
        thread_id: UUID,
        request: Request,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """透传 Server 的 runs/stream；前端 SDK 原生接收事件。"""
    sess = await session_service.get_writable_session(db_session, thread_id, user)

    body = await request.json()
    tid = str(thread_id)

    # 保留前端传入的 input/command/stream_mode；注入服务端控制参数
    body["assistant_id"] = "tutor"
    body["context"] = await session_service.build_agent_context(db_session, sess) # todo /src/tutoring/agent/prompts.py 探索跟这个聚合，提高工程化
    body["multitask_strategy"] = "reject"
    body["on_disconnect"] = "continue"
    body.setdefault("if_not_exists", "create")

    is_input = "input" in body
    is_command = "command" in body
    interrupted = await server_client.is_interrupted(tid)

    if is_input and interrupted:
        raise AppError(409, "SESSION_INTERRUPTED", "Session is paused at a quiz; call /quiz/resume first")
    if is_command and not interrupted:
        raise AppError(409, "SESSION_NOT_INTERRUPTED", "Session is not paused; no quiz to resume")

    if is_input:
        await session_service.touch_session(db_session, thread_id)

    return StreamingResponse(
        server_client.proxy_run_stream(tid, body),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )

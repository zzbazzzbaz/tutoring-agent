"""Chat SSE 端点 + 流式编排：send_message + quiz resume。

流式编排逻辑（原 agent/runtime.py）内联于此：
- agent.astream_events(version="v3") 返回 AsyncGraphRunStream 对象
- stream.messages -> 异步可迭代的消息对象；message.text -> 异步可迭代的 token
- stream.interrupted() -> awaitable bool（注意：是 async 方法，不是属性！）
- stream.interrupts() -> awaitable list[Interrupt]（同上）
- Command(resume=value) 从 interrupt 恢复
"""
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.agent.prompts import AgentContext
from tutoring.chat import service as chat_service
from tutoring.chat.schemas import QuizResumeRequest, SendMessageRequest
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def stream_chat(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """首次发送消息 -> SSE 流。

    Yields SSE 格式字符串：
        event: text\\ndata: {...}\\n\\n
        event: quiz_interrupt\\ndata: {...}\\n\\n
        event: done\\ndata: {}\\n\\n
        event: error\\ndata: {...}\\n\\n
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("stream_chat 失败")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def resume_quiz(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    db_session: AsyncSession,
    context: AgentContext,
) -> AsyncIterator[str]:
    """提交答题 -> SSE 流继续。

    Yields 同 stream_chat 的事件类型（resume 时不会有 quiz_interrupt）。

    runtime context 不进 checkpoint，resume 时必须像 stream_chat 一样重新传入，
    否则 main_agent_system_prompt 中间件读 context 会拿到 None。
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
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
                yield _sse("text", {"content": token})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("resume_quiz 失败")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def _save_final_agent_message(
    agent: CompiledStateGraph, config: dict, db_session: AsyncSession, session_id: uuid.UUID
) -> None:
    """从 LangGraph state 取最终 AIMessage，持久化到 Message 表。"""
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if not messages:
        return
    final_msg = messages[-1]
    content = getattr(final_msg, "content", None)
    text = _extract_text(content)
    if text:
        await db.save_message(
            db_session, session_id=session_id, role="agent", content=text
        )


def _extract_text(content) -> str:
    """从 AIMessage.content 提取纯文本。

    处理两种格式：
    - str：直接返回
    - list[dict]：拼接所有 {"type":"text","text":"..."} 块
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


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

    await db.save_message(
        db_session, session_id=session_id, role="user", content=body.content
    )
    await db.touch_session(db_session, session_id)

    ctx = await chat_service.build_agent_context(db_session, sess)

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
            async for sse_frame in resume_quiz(
                agent, session_id, body.action, body.answer, db_session, ctx
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

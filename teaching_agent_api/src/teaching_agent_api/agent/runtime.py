"""Agent runtime：stream_chat() 和 resume_quiz() 异步生成器，emit SSE 帧。

LangChain 1.x 模式：
- agent.astream_events(version="v3") 返回 AsyncGraphRunStream 对象
  （需 await，因为 _apregel_stream_v3 是 async def）
- stream.messages -> 异步可迭代的消息对象；message.text -> 异步可迭代的 token
- stream.interrupted() -> awaitable bool（注意：是 async 方法，不是属性！）
- stream.interrupts() -> awaitable list[Interrupt]（同上）
- Command(resume=value) 从 interrupt 恢复
"""
import json
import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.db import repos as db

logger = logging.getLogger(__name__)


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
        # 1. 流式 token
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        # 2. 检查 interrupt（quiz_flow 触发）
        # 注意：interrupted() 是 async 方法，需 await
        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return  # session 暂停，不存 agent 消息

        # 3. 流正常结束 -> 存 agent 最终消息
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
) -> AsyncIterator[str]:
    """提交答题 -> SSE 流继续。

    Yields 同 stream_chat 的事件类型（resume 时不会有 quiz_interrupt）。
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
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        # resume 后不应再有 interrupt（单题流程）
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
    """从 LangGraph state 取最终 AIMessage，持久化到 Message 表。

    LangChain 1.x 的 AIMessage.content 可能是：
    - str：纯文本
    - list[dict]：结构化内容块 [{"type":"text","text":"..."}, ...]
    需统一提取为纯文本字符串。
    """
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

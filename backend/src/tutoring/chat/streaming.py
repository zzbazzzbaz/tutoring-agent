"""agent 执行与 SSE 事件生产（写侧），以及共享的 LangGraph 运行时工具。

- stream_config：LangGraph 运行配置，thread_id 绑定会话状态，
  recursion_limit 防止工具调用死循环。
- is_interrupted：会话是否停在 interrupt（即有未答 quiz）。
- iter_tool_calls：安全遍历一条消息的 tool_calls，兼容 dict / 对象 / 异步形态，
  供本模块与 history 共用。
- stream_message / stream_resume：两个对外的流式入口，分别对应"发新消息"和
  "恢复 quiz"，二者共用 _stream_agent_to_queue 完成"驱动 agent -> 把
  token/工具/quiz 事件推入 queue"的核心循环。
"""
import asyncio
import inspect
import logging
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from tutoring.agent.prompts import AgentContext
from tutoring.chat import tasks

logger = logging.getLogger(__name__)


def stream_config(session_id: uuid.UUID) -> RunnableConfig:
    return {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15, # 图的最大 super-step 数，防止工具调用死循环
    }


async def is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    """会话是否停在 interrupt（即有未答 quiz 等待恢复）。"""
    state = await agent.aget_state(stream_config(session_id))
    return bool(state.next)


def iter_tool_calls(message) -> list[tuple[str, dict]]:
    """把一条消息的 tool_calls 统一成 (name, args) 列表。

    LangChain 不同版本里 tool_calls 可能是 list[dict] 或 list[ToolCall] 对象，
    偶尔是 awaitable；解析失败返回空列表。
    """
    tc = getattr(message, "tool_calls", None)
    if not tc or inspect.isawaitable(tc):
        return []
    try:
        return [
            (
                call.get("name", "") if isinstance(call, dict) else getattr(call, "name", ""),
                call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {}),
            )
            for call in tc
        ]
    except TypeError:
        return []


def _yield_tool_starts(message) -> list[dict]:
    """从一条 AI 消息中提取"工具开始"事件。

    present_question 不发 tool_start（它走 quiz interrupt 流程），其余工具都发。
    """
    events: list[dict] = []
    for name, args in iter_tool_calls(message):
        if name and name != "present_question":
            events.append(
                {"event": "tool_start", "data": {"tool_name": name, "tool_input": args}}
            )
    return events


async def _stream_agent_to_queue(
        agent: CompiledStateGraph,
        agent_input,
        context: AgentContext,
        queue: asyncio.Queue,
        session_id: uuid.UUID,
) -> None:
    """驱动 agent 流式执行并把事件推入 queue 的核心循环。

    无论发新消息还是恢复 quiz，事件生产逻辑完全相同：
    1. astream_events 启动流；
    2. 逐条消息先发 tool_start，再逐 token 发 text；
    3. 若被 interrupt（quiz 暂停），发 quiz_interrupt；
    4. 正常结束发 done，异常发 error；
    5. finally 注销后台任务。
    """
    config = stream_config(session_id)
    try:
        stream = await agent.astream_events(
            agent_input, config=config, version="v3", context=context,
        )
        async for message in stream.messages:
            for ev in _yield_tool_starts(message):
                await queue.put(ev)
            async for token in message.text:
                await queue.put({"event": "text", "data": {"content": token}})

        if await stream.interrupted():
            for it in await stream.interrupts():
                await queue.put({"event": "quiz_interrupt", "data": it.value})

        await queue.put({"event": "done", "data": {}})
    except Exception as e:
        logger.exception("agent streaming failed for session %s", session_id)
        await queue.put(
            {"event": "error", "data": {"message": str(e), "code": "AGENT_ERROR"}}
        )
    finally:
        tasks.unregister(session_id)


async def stream_message(
        agent: CompiledStateGraph,
        session_id: uuid.UUID,
        user_msg: str,
        context: AgentContext,
        queue: asyncio.Queue,
) -> None:
    """发一条新消息并流式回传 agent 响应事件。"""
    await _stream_agent_to_queue(
        agent,
        {"messages": [HumanMessage(content=user_msg)]},
        context,
        queue,
        session_id,
    )


async def stream_resume(
        agent: CompiledStateGraph,
        session_id: uuid.UUID,
        action: str,
        answer: str | None,
        context: AgentContext,
        queue: asyncio.Queue,
) -> None:
    """恢复一个被 quiz 中断的会话（提交答案或跳过）并流式回传事件。"""
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""
    await _stream_agent_to_queue(
        agent,
        Command(resume=resume_value),
        context,
        queue,
        session_id,
    )

"""Agent 工厂：单例 agent 实例同时服务 free/project 模式。

LangChain 1.x 模式：create_agent + @dynamic_prompt 中间件 +
context_schema=AgentContext。System prompt 在每次 invoke 时通过
AgentContext（传给 astream_events 的 context= 参数）动态选择。
"""
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from teaching_agent_api.agent.llm import get_llm
from teaching_agent_api.agent.prompts import AgentContext, teaching_prompt
from teaching_agent_api.agent.tools import quiz_flow, search_knowledge

_agent_singleton: CompiledStateGraph | None = None


def _reset_agent_singleton() -> None:
    """重置 agent 单例。测试时每个 lifespan 重建 checkpointer 后需调用。"""
    global _agent_singleton
    _agent_singleton = None


def build_agent(checkpointer) -> CompiledStateGraph:
    """构建 agent 单例。幂等：后续调用返回缓存实例。

    Args:
        checkpointer: 已 .setup() 的 AsyncPostgresSaver 实例

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    global _agent_singleton
    if _agent_singleton is not None:
        return _agent_singleton

    _agent_singleton = create_agent(
        model=get_llm(),
        tools=[search_knowledge, quiz_flow],
        middleware=[teaching_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
    return _agent_singleton

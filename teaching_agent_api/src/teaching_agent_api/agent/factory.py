from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from teaching_agent_api.agent.llm import get_llm
from teaching_agent_api.agent.prompts import AgentContext, main_agent_system_prompt
from teaching_agent_api.agent.tools import quiz_flow, search_knowledge


def build_agent(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """构建 agent。每次调用都新建实例。

    生产环境由 FastAPI lifespan 调用一次，进程内天然单例；
    测试环境每个 lifespan 重建后调用得到新实例，无需手动重置。

    Args:
        checkpointer: 已 .setup() 的 BaseCheckpointSaver 实例
            （如 AsyncPostgresSaver）

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    return create_agent(
        model=get_llm(),
        tools=[search_knowledge, quiz_flow],
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )

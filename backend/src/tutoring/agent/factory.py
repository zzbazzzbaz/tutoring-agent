from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from lightrag import LightRAG

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import AgentContext, main_agent_system_prompt
from tutoring.agent.tools import make_tools


def build_agent(*, rag: LightRAG, checkpointer=None) -> CompiledStateGraph:
    """构建 agent。Server 路径不传 checkpointer（Server 运行时注入）。

    Args:
        rag: LightRAG SDK 实例（知识库查询）
        checkpointer: 仅遗留路径用；Server 托管时为 None

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    tools = make_tools(rag=rag)
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )

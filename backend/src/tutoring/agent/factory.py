from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import AgentContext, main_agent_system_prompt
from tutoring.agent.tools import TOOLS


def build_agent(*, checkpointer=None) -> CompiledStateGraph:
    """构建 agent。Server 路径不传 checkpointer（Server 运行时注入）。"""
    return create_agent(
        model=get_llm(),
        tools=TOOLS,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )

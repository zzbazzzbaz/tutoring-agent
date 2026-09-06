from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from teaching_agent.agent.middleware import build_middleware
from teaching_agent.agent.prompts import render_system_prompt
from teaching_agent.auth.schemas import AgentContextV1
from teaching_agent.infrastructure.llm import get_llm


def build_agent(context: AgentContextV1, *, tools: list[BaseTool]) -> CompiledStateGraph:
    return create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=render_system_prompt(context),
        middleware=build_middleware(context),
    )
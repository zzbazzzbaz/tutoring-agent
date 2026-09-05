from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from teaching_agent.agent.middleware import build_middleware
from teaching_agent.agent.prompts import render_system_prompt
from teaching_agent.auth.schemas import AgentContextV1
from teaching_agent.infrastructure.llm import get_llm


def build_agent(context: AgentContextV1, *, tools: list[BaseTool]) -> CompiledStateGraph:
    agent = create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=render_system_prompt(context),
        middleware=build_middleware(context),
    )
    # 显式覆盖 LangChain create_agent 默认的 recursion_limit=9999，
    # 防止模型陷入工具循环导致 token 无止境消耗。
    # 50 步 ≈ 24 次工具调用；正常教学对话每轮工具调用 1~3 次，足够且防护更严。
    return agent.with_config({"recursion_limit": 50})

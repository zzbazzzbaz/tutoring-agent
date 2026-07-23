import contextlib
from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph_sdk.runtime import ServerRuntime

from teaching_agent.agent.prompts import prompt_middleware
from teaching_agent.auth.models import AgentContextV1
from teaching_agent.infrastructure.lightrag import lightrag_client
from teaching_agent.infrastructure.llm import get_llm
from teaching_agent.tools import create_tools

_INTROSPECTION_CONTEXT = AgentContextV1(mode="free")


def build_agent(context: AgentContextV1, *, tools: list[BaseTool]) -> CompiledStateGraph:
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[prompt_middleware(context)],
    )


def _trusted_context(runtime: ServerRuntime) -> AgentContextV1:
    user = runtime.ensure_user()
    raw_context = getattr(user, "agent_context", None)
    if raw_context is None:
        return _INTROSPECTION_CONTEXT
    if hasattr(raw_context, "dict"):
        raw_context = raw_context.dict()
    return AgentContextV1.model_validate(raw_context)


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime) -> AsyncIterator[CompiledStateGraph]:
    async with lightrag_client() as client:
        yield build_agent(_trusted_context(runtime), tools=create_tools(client))

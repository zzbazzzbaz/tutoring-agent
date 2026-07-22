import contextlib

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langgraph_sdk.runtime import ServerRuntime

from teaching_agent.llm import get_llm
from teaching_agent.prompts import prompt_middleware
from teaching_agent.schemas import AgentContextV1
from teaching_agent.tools import TOOLS

_INTROSPECTION_CONTEXT = AgentContextV1(mode="free")


def build_agent(context: AgentContextV1) -> CompiledStateGraph:
    return create_agent(
        model=get_llm(),
        tools=TOOLS,
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
async def get_graph(runtime: ServerRuntime):
    yield build_agent(_trusted_context(runtime))

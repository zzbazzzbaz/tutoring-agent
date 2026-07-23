import contextlib
from collections.abc import AsyncIterator

from langgraph.graph.state import CompiledStateGraph
from langgraph_sdk.runtime import ServerRuntime

from teaching_agent.agent.factory import build_agent
from teaching_agent.auth.context import get_trusted_agent_context
from teaching_agent.infrastructure.lightrag import lightrag_client
from teaching_agent.tools import create_tools


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime) -> AsyncIterator[CompiledStateGraph]:
    async with lightrag_client() as client:
        yield build_agent(get_trusted_agent_context(runtime), tools=create_tools(client))

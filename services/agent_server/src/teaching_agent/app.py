import contextlib
from collections.abc import AsyncIterator

from langgraph.graph.state import CompiledStateGraph
from langgraph_sdk.runtime import ServerRuntime

from teaching_agent.agent.factory import build_agent
from teaching_agent.auth.context import get_trusted_agent_context
from teaching_agent.infrastructure.lightrag import lightrag_client
from teaching_agent.tools import create_tools
from teaching_agent.tools.case_design import create_save_case_draft_tool
from teaching_agent.tools.progress import create_report_stage_progress_tool


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime) -> AsyncIterator[CompiledStateGraph]:
    async with lightrag_client() as client:
        context = get_trusted_agent_context(runtime)
        tools = create_tools(client)
        if context.mode == "project":
            tools = [*tools, create_report_stage_progress_tool()]
        elif context.mode == "case_design":
            tools = [create_save_case_draft_tool()]
        yield build_agent(context, tools=tools)

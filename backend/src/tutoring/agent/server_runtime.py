"""LangGraph Server 入口：graph factory。"""
import contextlib

from langgraph_sdk.runtime import ServerRuntime

from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime[AgentContext]):
    """构建图；知识库检索由工具直接调用 LightRAG HTTP API。"""
    yield build_agent()

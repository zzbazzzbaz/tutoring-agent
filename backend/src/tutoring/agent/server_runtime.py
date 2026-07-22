"""LangGraph Server 入口：graph factory。

仅真实 run 时初始化 LightRAG（重资源），schema 内省时返回不连 rag 的轻量 agent。
checkpointer 由 Server 运行时注入，这里不传。
"""
import contextlib

from langgraph_sdk.runtime import ServerRuntime

from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext
from tutoring.core.lightrag import create_rag


def _build_introspect_agent():
    """内省/schema 用：不连 rag 的无工具 agent，避免生成 OpenAPI 时初始化 LightRAG。"""
    from langchain.agents import create_agent

    from tutoring.agent.llm import get_llm
    from tutoring.agent.prompts import main_agent_system_prompt

    return create_agent(
        model=get_llm(),
        tools=[],
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
    )


_introspect_agent = _build_introspect_agent()


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime[AgentContext]):
    if runtime.execution_runtime:           # 真实 run
        rag = create_rag()
        await rag.initialize_storages()
        try:
            yield build_agent(rag=rag)       # checkpointer 由 Server 注入
        finally:
            await rag.finalize_storages()
    else:                                    # Schema/内省
        yield _introspect_agent

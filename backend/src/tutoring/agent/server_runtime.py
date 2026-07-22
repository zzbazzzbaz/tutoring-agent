"""LangGraph Server 入口：graph factory。

仅真实 run 时初始化 LightRAG（重资源），schema 内省时返回不连 rag 的轻量 agent。
checkpointer 由 Server 运行时注入，这里不传。

LightRAG 构造是同步重操作（tiktoken 加载等），用 asyncio.to_thread 移出事件循环；
且做成进程级单例，只初始化一次（避免每个 run 重复 create_rag + initialize_storages）。
"""
import asyncio
import contextlib

from langgraph_sdk.runtime import ServerRuntime
from lightrag import LightRAG

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

# LightRAG 进程级单例（懒初始化）
_rag: LightRAG | None = None
_rag_lock = asyncio.Lock()


async def _get_rag() -> LightRAG:
    """懒初始化并复用 LightRAG 单例。

    create_rag() 是同步重操作（tiktoken 等），用 to_thread 移出事件循环；
    initialize_storages() 是 async，直接 await。只执行一次，后续 run 复用。
    """
    global _rag
    if _rag is None:
        async with _rag_lock:
            if _rag is None:
                rag = await asyncio.to_thread(create_rag)
                await rag.initialize_storages()
                _rag = rag
    return _rag


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime[AgentContext]):
    if runtime.execution_runtime:           # 真实 run
        rag = await _get_rag()
        yield build_agent(rag=rag)          # checkpointer 由 Server 注入
    else:                                    # Schema/内省
        yield _introspect_agent

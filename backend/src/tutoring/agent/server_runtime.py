"""LangGraph Server 入口：graph factory。

LightRAG 构造是同步重操作（tiktoken 等），用 asyncio.to_thread 移出事件循环；
做成进程级单例只初始化一次，避免每条消息都重建 LightRAG + 重连 PG/Neo4j。
checkpointer 由 Server 运行时注入，这里不传。
"""
import asyncio
import contextlib

from langgraph_sdk.runtime import ServerRuntime
from lightrag import LightRAG

from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext
from tutoring.core.lightrag import create_rag

_rag: LightRAG | None = None
_rag_lock = asyncio.Lock()


async def _get_rag() -> LightRAG:
    """懒初始化并复用 LightRAG 单例（双检锁，只初始化一次）。"""
    global _rag
    if _rag is None:
        async with _rag_lock:
            if _rag is None:
                rag = await asyncio.to_thread(create_rag)  # 同步重操作移出事件循环
                await rag.initialize_storages()
                _rag = rag
    return _rag


@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime[AgentContext]):
    """每次 run 用单例 rag 构建 agent；context 由客户端经 SDK 传入，context_schema 接管。"""
    rag = await _get_rag()
    yield build_agent(rag=rag)

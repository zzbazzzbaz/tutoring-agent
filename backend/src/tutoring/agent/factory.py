from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from lightrag import LightRAG
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import AgentContext, main_agent_system_prompt
from tutoring.agent.tools import make_tools


def build_agent(
    checkpointer: BaseCheckpointSaver,
    rag: LightRAG,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> CompiledStateGraph:
    """构建 agent。每次调用都新建实例。

    Args:
        checkpointer: 已 .setup() 的 BaseCheckpointSaver 实例
            （如 AsyncPostgresSaver）
        rag: LightRAG SDK 实例（知识库查询）
        db_session_factory: SQLAlchemy 异步 session factory

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    tools = make_tools(rag=rag, db_session_factory=db_session_factory)
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )

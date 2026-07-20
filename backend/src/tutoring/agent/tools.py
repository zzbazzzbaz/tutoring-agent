"""Agent 工具工厂：make_tools() 闭包注入依赖。

LangChain 1.x 模式：
- @tool(description=..., args_schema=...) 统一风格
- interrupt() 来自 langgraph.types，实现 HITL 暂停
- RunnableConfig 用于访问 thread_id（= session_id）
- make_tools() 由 build_agent() 调用，闭包捕获 LightRAGClient + db_session_factory

工具内部零 LLM 调用--出题和评估全部由主智能体在推理中完成。
"""
import logging
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.schemas import PresentQuestionArgs, SearchKnowledgeArgs
from tutoring.db import repos
from tutoring.knowledge.client import LightRAGClient

logger = logging.getLogger(__name__)


def make_tools(
    *,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> list[BaseTool]:
    """构建 agent 工具列表，闭包捕获依赖。

    由 build_agent() 调用，测试可独立构造工具而无需碰全局态。
    """

    @asynccontextmanager
    async def _db_session():
        """工具内部获取 DB session 的异步上下文管理器。"""
        async with db_session_factory() as session:
            yield session

    @tool(
        description="检索课程知识库（知识图谱 + RAG），返回相关知识片段。当学生提问或讨论某个概念时，先调用此工具检索相关知识，再基于检索内容设计追问或出题。",
        args_schema=SearchKnowledgeArgs,
    )
    async def search_knowledge(query: str) -> str:
        try:
            result = await lightrag_client.query(
                query=query,
                mode="mix",
                only_need_context=True,
                include_references=True,
            )
        except Exception as e:
            logger.exception("search_knowledge 失败")
            return f"知识库检索失败: {e}"

        context = (result.get("response") or "").strip()
        if not context:
            return "未检索到相关内容，该问题可能超出当前课程知识库范围"
        return context

    @tool(
        description="向学生展示一道题目并等待作答。调用后会暂停等待学生答题，学生提交后返回其答案。拿到答案后请自行评估对错并在回复中给学生反馈。",
        args_schema=PresentQuestionArgs,
    )
    async def present_question(
        topic: str,
        q_type: Literal["single", "multi", "short"],
        stem: str,
        options: list[str] | None,
        answer: str,
        analysis: str,
        config: RunnableConfig,
    ) -> dict:
        from langgraph.types import interrupt

        session_id = UUID(config["configurable"]["thread_id"])

        async with _db_session() as db_session:
            quiz = await repos.upsert_pending_question(
                db_session,
                session_id=session_id,
                topic=topic,
                q_type=q_type,
                stem=stem,
                options=options,
                answer=answer,
                analysis=analysis,
            )

        student_answer = interrupt(
            {
                "question_id": str(quiz.id),
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        if student_answer.get("action") == "skip":
            async with _db_session() as db_session:
                await repos.update_question(db_session, quiz.id, status="skipped")
            return {"question_id": str(quiz.id), "action": "skipped"}

        user_answer = student_answer.get("answer", "")
        async with _db_session() as db_session:
            await repos.update_question(
                db_session,
                quiz.id,
                status="answered",
                user_answer=user_answer,
            )

        return {"question_id": str(quiz.id), "student_answer": user_answer}

    return [search_knowledge, present_question]

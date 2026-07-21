import logging
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from lightrag import LightRAG, QueryParam
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.schemas import PresentQuestionArgs, SearchKnowledgeArgs
from tutoring.db import repos

logger = logging.getLogger(__name__)


def make_tools(
    *,
    rag: LightRAG,
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
            result = await rag.aquery(
                query,
                param=QueryParam(
                    mode="mix",
                    only_need_context=True,
                    top_k=15,
                    chunk_top_k=10,
                    max_entity_tokens=3000,
                    max_relation_tokens=3000,
                    max_total_tokens=8000,
                    enable_rerank=False,
                ),
            )
        except Exception as e:
            logger.exception("search_knowledge 失败")
            return f"知识库检索失败: {e}"

        if not result or not result.strip():
            return "未检索到相关内容，该问题可能超出当前课程知识库范围"
        return result

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

        quiz_data = repos.QuizEventData(
            topic=topic, q_type=q_type, stem=stem,
            options=options, answer=answer, analysis=analysis,
        ).model_dump()

        async with _db_session() as db_session:
            quiz_event = await repos.save_event(
                db_session, session_id=session_id,
                type="quiz", data=quiz_data, status="pending",
            )

        student_answer = interrupt(
            {
                "question_id": str(quiz_event.id),
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        if student_answer.get("action") == "skip":
            async with _db_session() as db_session:
                await repos.update_quiz_status(
                    db_session, quiz_event.id, status="skipped",
                )
            return {"question_id": str(quiz_event.id), "action": "skipped"}

        user_answer = student_answer.get("answer", "")
        async with _db_session() as db_session:
            await repos.update_quiz_status(
                db_session, quiz_event.id,
                status="answered", user_answer=user_answer,
            )

        return {"question_id": str(quiz_event.id), "student_answer": user_answer}

    return [search_knowledge, present_question]

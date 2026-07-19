"""Agent 工具工厂：make_tools() 闭包注入依赖，替代模块级全局态。

LangChain 1.x 模式：
- @tool 装饰器来自 langchain_core.tools
- with_structured_output(method="function_calling") 获取类型化 LLM 响应
- interrupt() 来自 langgraph.types，实现 HITL 暂停
- RunnableConfig 用于访问 thread_id（= session_id）
- make_tools() 由 lifespan 调用，闭包捕获 LightRAGClient + db_session_factory

结构化输出 schema（QuizOutput / EvaluationOutput）位于 agent.schemas。
"""
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import QUIZ_GENERATION_PROMPT, EVALUATION_PROMPT
from tutoring.agent.schemas import EvaluationOutput, QuizOutput
from tutoring.core.config import settings
from tutoring.db import repos
from tutoring.knowledge.client import LightRAGClient

logger = logging.getLogger(__name__)


def make_tools(
    *,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> list[BaseTool]:
    """构建 agent 工具列表，闭包捕获依赖。

    替代原模块级 _state + set_dependencies()。lifespan 启动时调用一次，
    测试可独立构造工具而无需碰全局态。
    """

    @asynccontextmanager
    async def _db_session():
        """工具内部获取 DB session 的异步上下文管理器。"""
        async with db_session_factory() as session:
            yield session

    async def _search_for_quiz(topic: str) -> str:
        """出题前先检索相关知识作为素材。"""
        try:
            result = await lightrag_client.query(query=topic, mode="mix", only_need_context=True)
            return result.get("response", "") or ""
        except Exception as e:
            logger.warning("出题素材检索失败: %s", e)
            return ""

    async def _generate_quiz(topic: str, context: str) -> QuizOutput:
        """LLM 结构化出题。"""
        llm = get_llm().with_structured_output(QuizOutput, method="function_calling")
        return await llm.ainvoke(
            QUIZ_GENERATION_PROMPT.format(
                course_name=settings.course_name,
                topic=topic,
                context=context or "（无检索结果）",
            )
        )

    async def _evaluate_answer(
        stem: str, q_type: str, correct_answer: str, user_answer: str
    ) -> EvaluationOutput:
        """LLM 结构化评估。"""
        llm = get_llm().with_structured_output(EvaluationOutput, method="function_calling")
        return await llm.ainvoke(
            EVALUATION_PROMPT.format(
                stem=stem,
                q_type=q_type,
                correct_answer=correct_answer,
                student_answer=user_answer,
            )
        )

    @tool
    async def search_knowledge(query: str) -> str:
        """检索课程知识库（知识图谱 + RAG），返回相关知识片段。

        当学生提问或讨论某个概念时，先调用此工具检索相关知识，
        再基于检索内容设计苏格拉底式追问。检索结果包含向量匹配和知识图谱扩展的片段。

        Args:
            query: 检索关键词，需包含完整上下文（消除代词指代）
        """
        try:
            result = await lightrag_client.query(
                query=query,
                mode="mix",  # KG + 向量，LightRAG 推荐
                only_need_context=True,  # 不调 LightRAG 的 LLM，agent 自带 LLM
                include_references=True,
            )
        except Exception as e:
            logger.exception("search_knowledge 失败")
            return f"知识库检索失败: {e}"

        context = (result.get("response") or "").strip()
        if not context:
            return "未检索到相关内容，该问题可能超出当前课程知识库范围"
        return context

    @tool
    async def quiz_flow(topic: str, config: RunnableConfig) -> str:
        """出一道关于指定知识点的题目，等待学生作答后返回评估结果。

        当学生说"考考我"、需要检验理解程度、或你判断时机成熟时调用此工具。
        调用后会暂停等待学生答题，学生提交答案后自动判分。

        Args:
            topic: 要出题的知识点名称
        """
        # 延迟导入：避免 import 时硬依赖 langgraph.types
        from langgraph.types import interrupt

        session_id_str = config["configurable"]["thread_id"]
        session_id = UUID(session_id_str)

        # === 幂等检查（resume 时复用，避免重复出题）===
        # 注意：interrupt() 之前的代码在 resume 时会重新执行，
        # get_pending_question + upsert_pending_question 组合保证出题只发生一次。
        async with _db_session() as db_session:
            pending = await repos.get_pending_question(db_session, session_id, topic)
            if pending:
                quiz = pending
            else:
                # 首次调用：检索 + 生成
                context = await _search_for_quiz(topic)
                quiz_data = await _generate_quiz(topic, context)
                quiz = await repos.upsert_pending_question(
                    db_session,
                    session_id=session_id,
                    topic=topic,
                    q_type=quiz_data.q_type,
                    stem=quiz_data.stem,
                    options=quiz_data.options,
                    answer=quiz_data.answer,
                    analysis=quiz_data.analysis,
                )

        # === interrupt：首次调用时暂停，resume 时返回学生答案 ===
        student_answer = interrupt(
            {
                "question_id": str(quiz.id),
                "topic": topic,
                "q_type": quiz.q_type,
                "stem": quiz.stem,
                "options": quiz.options,
            }
        )

        # === 以下仅在 resume 时执行一次 ===
        async with _db_session() as db_session:
            if student_answer.get("action") == "skip":
                await repos.update_question(db_session, quiz.id, status="skipped")
                return "学生跳过了本题。请继续对话，了解学生的疑虑。"

            answer = student_answer.get("answer", "")
            evaluation = await _evaluate_answer(
                stem=quiz.stem,
                q_type=quiz.q_type,
                correct_answer=quiz.answer,
                user_answer=answer,
            )
            await repos.update_question(
                db_session,
                quiz.id,
                status="answered",
                user_answer=answer,
                verdict=evaluation.verdict,
                diagnosis=evaluation.diagnosis,
            )

        return (
            f"判定: {evaluation.verdict}\n"
            f"错因诊断: {evaluation.diagnosis}\n"
            f"正确答案: {quiz.answer}\n"
            f"解析: {evaluation.analysis}"
        )

    return [search_knowledge, quiz_flow]

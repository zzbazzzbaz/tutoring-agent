import json
import logging
from typing import Literal

from langchain_core.tools import BaseTool, tool
from lightrag import LightRAG, QueryParam

from tutoring.agent.schemas import PresentQuestionArgs, SearchKnowledgeArgs

logger = logging.getLogger(__name__)


def make_tools(*, rag: LightRAG) -> list[BaseTool]:
    """构建 agent 工具列表，闭包捕获 rag 依赖。"""

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
        description="向学生展示一道题目并等待作答。调用后会暂停等待学生答题，学生提交后返回其答案。拿到答案后请基于你的专业知识自行评估对错并在回复中给学生反馈。",
        args_schema=PresentQuestionArgs,
    )
    async def present_question(
        topic: str,
        q_type: Literal["single", "multi", "short"],
        stem: str,
        options: list[str] | None,
    ) -> dict:
        from langgraph.types import interrupt
        import uuid as _uuid

        quiz_id = str(_uuid.uuid4())
        student_answer = interrupt(
            {
                "question_id": quiz_id,
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        # 归一化 resume 值为 dict：
        # - dict（网关 SDK）：直接用
        # - str 是 JSON 编码的 dict（Studio 填了 JSON 文本）：json.loads 解开
        # - str 是裸答案（Studio 直接填答案文本）：包成 {"answer": ...}
        if isinstance(student_answer, str):
            try:
                parsed = json.loads(student_answer)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            student_answer = parsed if isinstance(parsed, dict) else {"answer": student_answer}
        elif not isinstance(student_answer, dict):
            student_answer = {"answer": str(student_answer) if student_answer is not None else ""}

        if student_answer.get("action") == "skip":
            return {"question_id": quiz_id, "action": "skipped"}
        return {"question_id": quiz_id, "student_answer": student_answer.get("answer", "")}

    return [search_knowledge, present_question]

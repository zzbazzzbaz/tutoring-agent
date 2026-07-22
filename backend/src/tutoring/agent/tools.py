import logging
from typing import Literal

import httpx
from langchain_core.tools import BaseTool, tool

from tutoring.agent.schemas import PresentQuestionArgs, QuizResume, SearchKnowledgeArgs

logger = logging.getLogger(__name__)
LIGHTRAG_QUERY_URL = "http://localhost:19621/query"


@tool(
    description="检索课程知识库（知识图谱 + RAG），返回相关知识片段。当学生提问或讨论某个概念时，先调用此工具检索相关知识，再基于检索内容设计追问或出题。",
    args_schema=SearchKnowledgeArgs,
)
async def search_knowledge(query: str) -> str:
    """通过 LightRAG HTTP API 检索课程知识库。"""
    payload = {
        "query": query,
        "mode": "mix",
        "only_need_context": True,
        "top_k": 15,
        "chunk_top_k": 10,
        "max_entity_tokens": 3000,
        "max_relation_tokens": 3000,
        "max_total_tokens": 8000,
        "enable_rerank": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(LIGHTRAG_QUERY_URL, json=payload)
            response.raise_for_status()
        result = response.json().get("response", "")
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("search_knowledge 失败")
        return f"知识库检索失败: {exc}"

    if not isinstance(result, str) or not result.strip():
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

    resume = QuizResume.model_validate(student_answer)
    if resume.action == "skip":
        return {"question_id": quiz_id, "action": "skipped"}
    return {"question_id": quiz_id, "student_answer": resume.answer}


TOOLS: list[BaseTool] = [search_knowledge, present_question]

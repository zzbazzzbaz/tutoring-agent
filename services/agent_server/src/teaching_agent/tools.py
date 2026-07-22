import logging
from typing import Literal
from uuid import uuid4

import httpx
from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt

from teaching_agent.config import get_settings
from teaching_agent.schemas import PresentQuestionArgs, QuizResume, SearchKnowledgeArgs

logger = logging.getLogger(__name__)


@tool(
    description="检索课程知识库（知识图谱 + RAG），返回相关知识片段。",
    args_schema=SearchKnowledgeArgs,
)
async def search_knowledge(query: str) -> str:
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
            response = await client.post(get_settings().lightrag_query_url, json=payload)
            response.raise_for_status()
        result = response.json().get("response", "")
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("Knowledge search failed")
        return f"知识库检索失败: {exc}"
    if not isinstance(result, str) or not result.strip():
        return "未检索到相关内容，该问题可能超出当前课程知识库范围"
    return result


@tool(
    description="向学生展示一道题目并等待作答，拿到答案后自行评估并反馈。",
    args_schema=PresentQuestionArgs,
)
async def present_question(
    topic: str,
    q_type: Literal["single", "multi", "short"],
    stem: str,
    options: list[str] | None,
) -> dict:
    question_id = str(uuid4())
    student_answer = interrupt(
        {
            "question_id": question_id,
            "topic": topic,
            "q_type": q_type,
            "stem": stem,
            "options": options,
        }
    )
    resume = QuizResume.model_validate(student_answer)
    if resume.action == "skip":
        return {"question_id": question_id, "action": "skipped"}
    return {"question_id": question_id, "student_answer": resume.answer}


TOOLS: list[BaseTool] = [search_knowledge, present_question]

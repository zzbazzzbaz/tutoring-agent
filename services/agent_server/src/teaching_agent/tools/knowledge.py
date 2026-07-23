import logging

from langchain_core.tools import BaseTool, tool

from teaching_agent.infrastructure.lightrag import LightRAGClient, LightRAGError
from teaching_agent.tools.schemas import SearchKnowledgeArgs

logger = logging.getLogger(__name__)


def create_search_knowledge_tool(lightrag_client: LightRAGClient) -> BaseTool:
    @tool(
        description="检索课程知识库（知识图谱 + RAG），返回相关知识片段。",
        args_schema=SearchKnowledgeArgs,
    )
    async def search_knowledge(query: str) -> str:
        try:
            return await lightrag_client.search(query)
        except LightRAGError:
            logger.exception("Knowledge search failed")
            return "知识库检索暂时不可用，请基于已有对话继续引导学生思考。"

    return search_knowledge

from langchain_core.tools import BaseTool

from teaching_agent.infrastructure.lightrag import LightRAGClient
from teaching_agent.tools.knowledge import create_search_knowledge_tool
from teaching_agent.tools.quiz import present_question


def create_tools(lightrag_client: LightRAGClient) -> list[BaseTool]:
    return [create_search_knowledge_tool(lightrag_client), present_question]

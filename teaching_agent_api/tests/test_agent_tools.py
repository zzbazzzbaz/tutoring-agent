"""make_tools 工厂测试：替代原模块级 _state 隐式注入。"""
from teaching_agent_api.agent.tools import make_tools
from teaching_agent_api.core.config import settings
from teaching_agent_api.core.database import create_engine, create_session_factory
from teaching_agent_api.knowledge.client import LightRAGClient


async def test_make_tools_returns_expected_tools():
    lightrag = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    engine = create_engine(settings.database_url)
    tools = make_tools(
        lightrag_client=lightrag,
        db_session_factory=create_session_factory(engine),
    )
    assert [t.name for t in tools] == ["search_knowledge", "quiz_flow"]
    await engine.dispose()

"""make_tools 工厂测试：替代原模块级 _state 隐式注入。"""
from tutoring.agent.tools import make_tools
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory
from tutoring.knowledge.client import LightRAGClient


async def test_make_tools_returns_expected_tools():
    lightrag = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    engine = create_engine(settings.database_url)
    tools = make_tools(
        lightrag_client=lightrag,
        db_session_factory=create_session_factory(engine),
    )
    assert [t.name for t in tools] == ["search_knowledge", "present_question"]
    await engine.dispose()

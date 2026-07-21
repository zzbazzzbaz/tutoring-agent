"""测试 fixture：真实 ASGI client + 测试数据清理。

不 mock 模型/LightRAG/DB，直接调真实 API。
用 httpx.ASGITransport 绕过网络层，进程内调 FastAPI app。

每个测试重建 lifespan，build_agent 不再缓存单例，自然引用新 checkpointer。
"""
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from tutoring.core.config import settings
from tutoring.core.database import create_engine
from tutoring.main import app


@pytest_asyncio.fixture
async def client():
    """每个测试启动一次 lifespan，得到引用新 checkpointer 的 agent 实例。

    startup_timeout=60：远程 DB 的 init_db + checkpointer.setup 约 15s，
    默认 5s 超时会导致 lifespan 启动失败。
    """
    async with LifespanManager(app, startup_timeout=60):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", timeout=120
        ) as c:
            yield c


@pytest_asyncio.fixture
async def cleanup_db():
    """每个测试后清理测试数据。"""
    yield
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM chat_event"))
        await conn.execute(text("DELETE FROM session"))
        await conn.execute(text("DELETE FROM project"))
        await conn.execute(text("DELETE FROM checkpoint_writes"))
        await conn.execute(text("DELETE FROM checkpoint_blobs"))
        await conn.execute(text("DELETE FROM checkpoints"))
    await engine.dispose()

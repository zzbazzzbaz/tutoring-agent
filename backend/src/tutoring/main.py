"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from tutoring.core.config import settings, setup_langsmith

setup_langsmith()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from tutoring.core.database import create_engine, create_session_factory, init_db
from tutoring.core.errors import register_exception_handlers
from tutoring.core import health as health_router
from tutoring.projects import router as projects_router
from tutoring.chat import router as chat_rest_router
from tutoring.chat import sse as chat_sse_router
from tutoring.knowledge import router as knowledge_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. DB 引擎 + 业务表
    engine = create_engine(settings.database_url)
    await init_db(engine)
    db_session_factory = create_session_factory(engine)
    logger.info("DB initialized: %s", settings.database_url)

    # 2. LangGraph AsyncPostgresSaver
    # psycopg（内部使用）不接受 SQLAlchemy 的 "+asyncpg" 驱动后缀，
    # 因此需剥除为纯 postgres URL。
    pg_conn_str = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(pg_conn_str) as checkpointer:
        await checkpointer.setup()  # 幂等
        logger.info("LangGraph checkpointer ready")

        # 3. LightRAG 客户端
        from tutoring.knowledge.client import LightRAGClient
        lightrag_client = LightRAGClient(
            base_url=settings.lightrag_base_url,
            api_key=settings.lightrag_api_key,
        )
        await lightrag_client.start()
        logger.info("LightRAG client started: %s", settings.lightrag_base_url)

        # 4. 构建工具（闭包注入 LightRAGClient + DB session factory）
        from tutoring.agent.tools import make_tools
        tools = make_tools(
            lightrag_client=lightrag_client,
            db_session_factory=db_session_factory,
        )

        # 5. 构建 agent 单例
        app.state.agent = None
        try:
            from tutoring.agent.factory import build_agent
            app.state.agent = build_agent(checkpointer, tools)
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent 构建失败: %s", e)
            app.state.agent = None

        # 注入状态
        app.state.engine = engine
        app.state.db_session_factory = db_session_factory
        app.state.checkpointer = checkpointer
        app.state.lightrag_client = lightrag_client

        yield

    # 清理
    await lightrag_client.close()
    await engine.dispose()
    logger.info("Cleanup complete")


app = FastAPI(title="Teaching Agent API", version="0.2.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(projects_router.router)
app.include_router(chat_rest_router.router)
app.include_router(chat_sse_router.router)
app.include_router(knowledge_router.router)

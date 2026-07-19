"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from teaching_agent_api.config import settings
from teaching_agent_api.db.engine import create_engine, create_session_factory, init_db
from teaching_agent_api.api import health as health_router
from teaching_agent_api.api import projects as projects_router
from teaching_agent_api.api import sessions as sessions_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
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

        # 3. LightRAG 客户端（占位；T2 中完整实现）
        from teaching_agent_api.lightrag.client import LightRAGClient
        lightrag_client = LightRAGClient(
            base_url=settings.lightrag_base_url,
            api_key=settings.lightrag_api_key,
        )
        await lightrag_client.start()
        logger.info("LightRAG client started: %s", settings.lightrag_base_url)

        # 4. Agent（占位；T3 中完整实现）
        app.state.agent = None  # T3 将填充

        # 注入状态
        app.state.engine = engine
        app.state.db_session_factory = db_session_factory
        app.state.checkpointer = checkpointer
        app.state.lightrag_client = lightrag_client

        # T3 将在此构建 agent；目前为占位
        try:
            from teaching_agent_api.agent.factory import build_agent
            app.state.agent = build_agent(checkpointer)
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent not built yet (expected before T3): %s", e)
            app.state.agent = None

        yield

    # 清理
    await lightrag_client.close()
    await engine.dispose()
    logger.info("Cleanup complete")


app = FastAPI(title="Teaching Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(projects_router.router)
app.include_router(sessions_router.router)

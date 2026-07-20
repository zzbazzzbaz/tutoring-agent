import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import numpy as np
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import wrap_embedding_func_with_attrs

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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# --- LightRAG LLM / Embedding 函数（DashScope OpenAI 兼容） ---

async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    return await openai_complete_if_cache(
        settings.llm_model,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        **kwargs,
    )


@wrap_embedding_func_with_attrs(
    embedding_dim=settings.embedding_dim,
    max_token_size=8192,
    model_name=settings.embedding_model,
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embed.func(
        texts,
        model=settings.embedding_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. DB 引擎 + 业务表
    engine = create_engine(settings.database_url)
    await init_db(engine)
    db_session_factory = create_session_factory(engine)
    logger.info("DB initialized: %s", settings.database_url)

    # 2. LangGraph AsyncPostgresSaver
    pg_conn_str = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(pg_conn_str) as checkpointer:
        await checkpointer.setup()  # 幂等
        logger.info("LangGraph checkpointer ready")

        # 3. LightRAG SDK 实例（连同一个 PG + Neo4j）
        rag = LightRAG(
            workspace="default",
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            kv_storage="PGKVStorage",
            vector_storage="PGVectorStorage",
            graph_storage="Neo4JStorage",
            doc_status_storage="PGDocStatusStorage",
        )
        await rag.initialize_storages()
        logger.info("LightRAG SDK initialized")

        # 4. 构建 agent 单例
        app.state.agent = None
        try:
            from tutoring.agent.factory import build_agent
            app.state.agent = build_agent(
                checkpointer=checkpointer,
                rag=rag,
                db_session_factory=db_session_factory,
            )
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent 构建失败: %s", e)
            app.state.agent = None

        # 注入状态
        app.state.engine = engine
        app.state.db_session_factory = db_session_factory
        app.state.checkpointer = checkpointer
        app.state.rag = rag

        yield

        # 清理
        await rag.finalize_storages()

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

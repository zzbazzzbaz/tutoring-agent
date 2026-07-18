"""数据库引擎与会话工厂。"""
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from teaching_agent.config import settings

# async engine，连接 PostgreSQL + pgvector
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,   # 用前检测连接是否存活，防止复用死连接
    pool_recycle=3600,    # 1 小时回收连接，避免服务端超时断开
)

# 异步会话工厂
async_session_factory = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """创建所有业务表。

    LangGraph checkpoint 表由 AsyncPostgresSaver.setup() 自建，
    此处只创建 SQLModel 定义的业务表。
    """
    # 确保 models 被导入以注册所有表
    from teaching_agent import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """获取数据库会话（用于依赖注入或 notebook 中手动使用）。"""
    async with async_session_factory() as session:
        yield session

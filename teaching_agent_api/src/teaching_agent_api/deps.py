"""FastAPI 依赖。"""
from typing import AsyncIterator, Optional

from fastapi import Request, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.config import settings


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """每请求的 DB session。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-Id")) -> str:
    """无 header 时默认为 demo-student。"""
    return x_user_id or "demo-student"


def get_lightrag_client(request: Request):
    """从 app.state 获取 LightRAG 客户端单例。"""
    return request.app.state.lightrag_client


def get_agent(request: Request):
    """从 app.state 获取 Agent 单例。"""
    return request.app.state.agent

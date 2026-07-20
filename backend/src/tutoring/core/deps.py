"""FastAPI 依赖注入。"""
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import Request, Header
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass(frozen=True)
class CurrentUser:
    """当前请求用户。未来由 auth/ 模块的 JWT 校验填充 role。"""

    id: str
    role: str = "student"


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """每请求的 DB session。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


def get_current_user(x_user_id: str | None = Header(None, alias="X-User-Id")) -> CurrentUser:
    """无 header 时默认为 demo-student。未来改为委托 auth/ 模块校验 JWT。"""
    return CurrentUser(id=x_user_id or "demo-student")


def get_agent(request: Request) -> CompiledStateGraph:
    """从 app.state 获取 Agent 单例。"""
    return request.app.state.agent

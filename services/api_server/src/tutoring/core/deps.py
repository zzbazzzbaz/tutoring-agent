from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.auth import service as auth_service
from tutoring.core.errors import AppError


@dataclass(frozen=True)
class CurrentUser:
    """当前请求用户，由 auth 模块 token 校验填充。"""

    id: UUID
    username: str
    role: str
    name: str


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """每请求的 DB session。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


async def get_current_user(
    authorization: str | None = Header(None),
    db_session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """从 Authorization: Bearer <token> 校验并返回当前用户。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "MISSING_TOKEN", "缺少 Authorization Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = await auth_service.verify_token(db_session, token)
    return CurrentUser(id=user.id, username=user.username, role=user.role, name=user.name)


def get_db_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """从 app.state 获取 DB session factory（后台任务用）。"""
    return request.app.state.db_session_factory

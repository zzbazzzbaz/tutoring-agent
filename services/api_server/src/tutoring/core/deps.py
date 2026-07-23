from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth import service as auth_service
from tutoring.core.errors import AppError


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    username: str
    role: Literal["student", "teacher"]
    name: str


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


async def get_current_user(
    authorization: str | None = Header(None),
    db_session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "MISSING_TOKEN", "缺少 Authorization Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = await auth_service.verify_token(db_session, token)
    return CurrentUser(id=user.id, username=user.username, role=user.role, name=user.name)

"""Async repository functions. No class (YAGNI)."""
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tutoring.db.models import AuthToken, Project, Session, User


# === User ===

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def create_user(
    session: AsyncSession, *, username: str, password_hash: str, role: str, name: str,
) -> User:
    obj = User(username=username, password_hash=password_hash, role=role, name=name)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_users_by_role(session: AsyncSession, role: str) -> list[User]:
    stmt = select(User).where(User.role == role).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    obj = await session.get(User, user_id)
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False


async def update_password(session: AsyncSession, user_id: UUID, password_hash: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )
    await session.commit()


# === AuthToken ===

async def create_token(session: AsyncSession, user_id: UUID) -> AuthToken:
    obj = AuthToken(token=uuid.uuid4().hex, user_id=user_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_token_with_user(session: AsyncSession, token: str) -> AuthToken | None:
    stmt = (
        select(AuthToken)
        .where(AuthToken.token == token)
        .options(selectinload(AuthToken.user))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def delete_token(session: AsyncSession, token: str) -> bool:
    stmt = select(AuthToken).where(AuthToken.token == token)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False


# === Session ===

async def create_session(
    session: AsyncSession, *, mode: str, user_id: UUID, project_id: UUID | None = None,
) -> Session:
    obj = Session(mode=mode, user_id=user_id, project_id=project_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_session(session: AsyncSession, session_id: UUID) -> Session | None:
    stmt = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.project))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_sessions(
    session: AsyncSession, *, user_id: UUID | None = None,
    mode: str | None = None, limit: int = 20, offset: int = 0,
) -> list[Session]:
    stmt = (
        select(Session)
        .options(selectinload(Session.project))
        .where(Session.deleted_at.is_(None))
    )
    if user_id is not None:
        stmt = stmt.where(Session.user_id == user_id)
    if mode:
        stmt = stmt.where(Session.mode == mode)
    stmt = stmt.order_by(Session.last_active_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def touch_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(last_active_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def delete_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()


# === Project ===

async def create_project(session: AsyncSession, *, name: str, background_md: str, status: str = "draft") -> Project:
    obj = Project(name=name, background_md=background_md, status=status)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def list_projects(session: AsyncSession, *, status: str | None = None) -> list[Project]:
    stmt = select(Project).where(Project.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_project(session: AsyncSession, project_id: UUID, **fields) -> Project | None:
    await session.execute(update(Project).where(Project.id == project_id).values(**fields))
    await session.commit()
    return await session.get(Project, project_id)


async def delete_project(session: AsyncSession, project_id: UUID) -> None:
    await session.execute(
        update(Project).where(Project.id == project_id).values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()

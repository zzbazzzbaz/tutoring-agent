# 会话学习进度--业务逻辑
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Session, SessionProgress


async def update_progress(
    db: AsyncSession,
    *,
    session_id: UUID,
    progress: dict,
) -> None:
    """校验会话存在后，合并写入会话进度。"""
    session = await db.get(Session, session_id)
    if not session or session.deleted_at is not None:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    await repos.upsert_session_progress(db, session_id=session_id, progress=progress)


async def get_progress(
    db: AsyncSession,
    *,
    session_id: UUID,
) -> SessionProgress:
    session = await db.get(Session, session_id)
    if not session or session.deleted_at is not None:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    existing = await repos.get_session_progress(db, session_id=session_id)
    if existing is None:
        return SessionProgress(session_id=session_id, progress={})
    return existing

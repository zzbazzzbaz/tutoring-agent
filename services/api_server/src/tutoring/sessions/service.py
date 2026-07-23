import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Session


async def _load_session(db: AsyncSession, session_id: uuid.UUID) -> Session:
    """加载会话，不存在则 404。"""
    sess = await repos.get_session(db, session_id)
    if not sess or sess.deleted_at is not None:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    return sess


async def get_readable_session(
    db: AsyncSession, session_id: uuid.UUID, user: CurrentUser
) -> Session:
    """加载会话；学生只能读自己的，教师可读任意。"""
    sess = await _load_session(db, session_id)
    if user.role == "student" and sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def get_writable_session(
    db: AsyncSession, session_id: uuid.UUID, user: CurrentUser
) -> Session:
    """加载会话；无论角色都必须是本人。"""
    sess = await _load_session(db, session_id)
    if sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def touch_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """更新会话最后活跃时间。"""
    await repos.touch_session(db, session_id)


def session_to_out_dict(sess: Session) -> dict:
    """把 Session ORM 序列化为 API 输出 dict。"""
    data = {
        "id": sess.id,
        "user_id": sess.user_id,
        "mode": sess.mode,
        "project_id": sess.project_id,
        "title": sess.title,
        "last_active_at": sess.last_active_at,
        "created_at": sess.created_at,
    }
    if sess.project is not None:
        data["project_name"] = sess.project.name
    return data

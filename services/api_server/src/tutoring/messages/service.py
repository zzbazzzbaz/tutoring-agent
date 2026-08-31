# 消息记录--业务逻辑
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Session
from tutoring.messages.schemas import AgentMessageItem


async def persist_agent_messages(
    db: AsyncSession,
    *,
    session_id: UUID,
    items: list[AgentMessageItem],
) -> int:
    """校验会话存在后，批量写入消息记录。返回写入条数。"""
    session = await db.get(Session, session_id)
    if not session or session.deleted_at is not None:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if not items:
        return 0
    return await repos.create_messages(
        db,
        session_id=session_id,
        items=[i.model_dump() for i in items],
    )

"""chat 模块的 REST 入口：会话历史重建。

session CRUD 见 sessions/router.py；流式代理见 proxy.py。
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.chat import history as chat_history
from tutoring.chat.schemas import HistoryOut
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.sessions import service as session_service

router = APIRouter(tags=["chat"])


@router.get("/sessions/{session_id}/history", response_model=HistoryOut)
async def get_history(
        session_id: UUID,
        user: CurrentUser = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db),
) -> HistoryOut:
    await session_service.get_readable_session(db_session, session_id, user)
    result = await chat_history.build_history(str(session_id))
    return HistoryOut(**result)

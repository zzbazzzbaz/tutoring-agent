"""Session CRUD + History endpoint."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.chat import service as chat_service
from tutoring.chat.schemas import HistoryOut, SessionCreate, SessionOut
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.db import repos
from tutoring.projects import service as project_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    project_obj = None
    if body.mode == "project":
        project_obj = await project_service.get_published_project(db_session, body.project_id)
    sess = await repos.create_session(
        db_session, mode=body.mode, user_id=user.id, project_id=body.project_id
    )
    sess.project = project_obj
    return SessionOut.model_validate(chat_service.session_to_out_dict(sess))


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    mode: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    sessions = await repos.list_sessions(
        db_session, user_id=user.id, mode=mode, limit=limit, offset=offset,
    )
    return [SessionOut.model_validate(chat_service.session_to_out_dict(s)) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    sess = await chat_service.get_readable_session(db_session, session_id, user)
    return SessionOut.model_validate(chat_service.session_to_out_dict(sess))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    await chat_service.get_writable_session(db_session, session_id, user)
    await repos.delete_session(db_session, session_id)


@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> HistoryOut:
    await chat_service.get_readable_session(db_session, session_id, user)
    result = await chat_service.build_history(db_session, session_id)
    return HistoryOut(**result)

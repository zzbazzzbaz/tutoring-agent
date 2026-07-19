"""Session CRUD + 消息 + 题目端点。"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.chat import service as chat_service
from teaching_agent_api.chat.schemas import (
    SessionCreate,
    SessionOut,
    MessageOut,
    QuestionOut,
)
from teaching_agent_api.core.deps import CurrentUser, get_current_user, get_db
from teaching_agent_api.db import repos
from teaching_agent_api.projects import service as project_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    project_obj = None
    if body.mode == "project":
        # get_published_project 返回（已 fetch 的）Project；将其传给
        # session_to_out_dict 以避免第二次 lazy-load round-trip。
        project_obj = await project_service.get_published_project(db_session, body.project_id)
    sess = await repos.create_session(
        db_session, mode=body.mode, user_id=user.id, project_id=body.project_id
    )
    return SessionOut.model_validate(chat_service.session_to_out_dict(sess, project=project_obj))


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    status_filter: str | None = Query(None, alias="status"),
    mode: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    sessions = await repos.list_sessions(
        db_session,
        user_id=user.id,
        status=status_filter,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    return [SessionOut.model_validate(chat_service.session_to_out_dict(s)) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    sess = await chat_service.get_owned_session(db_session, session_id, user.id)
    return SessionOut.model_validate(chat_service.session_to_out_dict(sess))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    await chat_service.get_owned_session(db_session, session_id, user.id)
    await repos.end_session(db_session, session_id)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await chat_service.get_owned_session(db_session, session_id, user.id)
    msgs = await repos.list_messages(db_session, session_id, limit=limit, offset=offset)
    return [MessageOut.model_validate(m) for m in msgs]


@router.get("/{session_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    session_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[QuestionOut]:
    await chat_service.get_owned_session(db_session, session_id, user.id)
    qs = await repos.list_questions(db_session, session_id, status=status_filter)
    return [QuestionOut.model_validate(q) for q in qs]

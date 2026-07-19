"""Session CRUD + 消息 + 题目端点。"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.db.models import Project, Session
from teaching_agent_api.deps import get_db, get_user_id
from teaching_agent_api.schemas.session import (
    SessionCreate,
    SessionOut,
    MessageOut,
    QuestionOut,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _validate_session_ownership(
    db_session: AsyncSession, session_id: UUID, user_id: str
) -> Session:
    """若 session 存在且属于该用户则返回，否则抛出。"""
    sess = await db.get_session(db_session, session_id)
    if not sess:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found",
                }
            },
        )
    if sess.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Session does not belong to user",
                }
            },
        )
    return sess


async def _validate_project(db_session: AsyncSession, project_id: UUID) -> Project:
    """确保引用的 project 存在且已发布。返回该 project，以便调用方
    无需额外的 lazy-load round-trip 即可填充 `project_name`。"""
    proj = await db.get_project(db_session, project_id)
    if not proj:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "PROJECT_NOT_FOUND",
                    "message": f"Project {project_id} not found",
                }
            },
        )
    if proj.status != "published":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "PROJECT_NOT_PUBLISHED",
                    "message": "Project must be published to start a session",
                }
            },
        )
    return proj


def _enrich_session(sess, project=None) -> dict:
    """从 Session ORM 实例构建 SessionOut dict，在可用时添加
    `project_name`。

    有两条路径会填充 `project_name`：
      1. 显式传入 `project` 参数（由 create_session 使用，因为它刚刚
         为校验而 fetch 了 project）。
      2. 通过 eager loading（selectinload）在 get_session / list_sessions
         中访问 `sess.project`。

    此处避免 `sess.model_dump()`，因为它会递归遍历 `project.sessions`
    及其它关系属性，开销较大且可能让调用方意外。手动字段选择显式且安全。
    """
    data = {
        "id": sess.id,
        "user_id": sess.user_id,
        "mode": sess.mode,
        "project_id": sess.project_id,
        "title": sess.title,
        "status": sess.status,
        "last_active_at": sess.last_active_at,
        "created_at": sess.created_at,
    }
    proj = project
    if proj is None:
        # `sess.project` 仅在查询使用 selectinload 时才加载；
        # 在未 eager loading 的情况下访问会触发 greenlet 错误
        # （在 async 上下文中），此处防御性吞掉。
        try:
            proj = sess.project
        except Exception:
            proj = None
    if proj is not None:
        data["project_name"] = proj.name
    return data


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    project_obj = None
    if body.mode == "project":
        # _validate_project 返回（已 fetch 的）Project；将其传给
        # _enrich_session 以避免第二次 lazy-load round-trip。
        project_obj = await _validate_project(db_session, body.project_id)
    sess = await db.create_session(
        db_session, mode=body.mode, user_id=user_id, project_id=body.project_id
    )
    return SessionOut.model_validate(_enrich_session(sess, project=project_obj))


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    status_filter: str | None = Query(None, alias="status"),
    mode: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    sessions = await db.list_sessions(
        db_session,
        user_id=user_id,
        status=status_filter,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    return [SessionOut.model_validate(_enrich_session(s)) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: UUID,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> SessionOut:
    sess = await _validate_session_ownership(db_session, session_id, user_id)
    return SessionOut.model_validate(_enrich_session(sess))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: UUID,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    await _validate_session_ownership(db_session, session_id, user_id)
    await db.end_session(db_session, session_id)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await _validate_session_ownership(db_session, session_id, user_id)
    msgs = await db.list_messages(db_session, session_id, limit=limit, offset=offset)
    return [MessageOut.model_validate(m) for m in msgs]


@router.get("/{session_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    session_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> list[QuestionOut]:
    await _validate_session_ownership(db_session, session_id, user_id)
    qs = await db.list_questions(db_session, session_id, status=status_filter)
    return [QuestionOut.model_validate(q) for q in qs]

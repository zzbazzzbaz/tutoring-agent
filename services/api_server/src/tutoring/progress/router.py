# 会话学习进度--路由
import hmac
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth import service as auth_service
from tutoring.auth.router import require_agent_server
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser, get_db
from tutoring.core.errors import AppError
from tutoring.db.models import Session
from tutoring.progress import service as progress_service
from tutoring.progress.schemas import (
    AgentProgressUpdate,
    AgentProgressUpdateResponse,
    SessionProgressOut,
)

router = APIRouter(prefix="/progress", tags=["progress"])


def _agent_server_ok(x_agent_server_secret: str | None) -> bool:
    return bool(
        x_agent_server_secret
        and hmac.compare_digest(x_agent_server_secret, settings.agent_server_secret)
    )


async def _maybe_user(
    authorization: str | None = Header(None),
    x_agent_server_secret: str | None = Header(None),
    db_session: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """内部调用（携带密钥）放行返回 None；否则校验用户 token 并返回当前用户。"""
    if _agent_server_ok(x_agent_server_secret):
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "MISSING_TOKEN", "缺少 Authorization Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = await auth_service.verify_token(db_session, token)
    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        name=user.name,
        avatar_url=user.avatar_url,
    )


@router.post(
    "/internal/agent",
    response_model=AgentProgressUpdateResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_agent_server)],
    tags=["internal-agent"],
)
async def write_agent_progress(
    body: AgentProgressUpdate,
    db_session: AsyncSession = Depends(get_db),
) -> AgentProgressUpdateResponse:
    """Agent Server 更新会话学习进度（内部端点，需 X-Agent-Server-Secret）。"""
    await progress_service.update_progress(
        db_session,
        session_id=body.session_id,
        progress=body.progress,
    )
    return AgentProgressUpdateResponse(updated=True)


@router.get("/sessions/{session_id}", response_model=SessionProgressOut)
async def get_session_progress(
    session_id: UUID,
    user: CurrentUser | None = Depends(_maybe_user),
    db_session: AsyncSession = Depends(get_db),
) -> SessionProgressOut:
    """查询某会话的学习进度。

    - 教师：可查任意会话
    - 学生：只能查自己的会话
    - Agent Server 内部调用（携带 X-Agent-Server-Secret）：放行
    """
    session = await db_session.get(Session, session_id)
    if not session or session.deleted_at is not None:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if user is not None and user.role != "teacher" and str(session.user_id) != str(user.id):
        raise AppError(403, "FORBIDDEN", "无权查看其他会话的进度")
    result = await progress_service.get_progress(db_session, session_id=session_id)
    return SessionProgressOut.model_validate(result)

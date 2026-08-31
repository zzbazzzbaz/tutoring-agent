# 项目学习进度--路由
import hmac
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth.router import require_agent_server
from tutoring.auth import service as auth_service
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.progress import service as progress_service
from tutoring.progress.schemas import (
    AgentProgressUpdate,
    AgentProgressUpdateResponse,
    ProjectProgressOut,
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
    """Agent Server 更新学生学习进度（内部端点，需 X-Agent-Server-Secret）。"""
    await progress_service.update_progress(
        db_session,
        user_id=body.user_id,
        project_id=body.project_id,
        progress=body.progress,
    )
    return AgentProgressUpdateResponse(updated=True)


@router.get("/projects/{project_id}/users/{user_id}", response_model=ProjectProgressOut)
async def get_user_project_progress(
    project_id: UUID,
    user_id: UUID,
    user: CurrentUser | None = Depends(_maybe_user),
    db_session: AsyncSession = Depends(get_db),
) -> ProjectProgressOut:
    """查询某学生某项目的学习进度。

    - 教师：可查任意学生
    - 学生：只能查自己
    - Agent Server 内部调用（携带 X-Agent-Server-Secret）：放行
    """
    if user is not None and user.role != "teacher" and str(user.id) != str(user_id):
        raise AppError(403, "FORBIDDEN", "无权查看其他学生的进度")
    result = await progress_service.get_progress(
        db_session, user_id=user_id, project_id=project_id
    )
    return ProjectProgressOut.model_validate(result)

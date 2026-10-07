from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth.router import require_agent_server
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.core.schemas import Page
from tutoring.db import repos
from tutoring.projects import service as project_service
from tutoring.projects.schemas import (
    AgentCaseDraftIn,
    AgentCaseDraftOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可执行此操作")


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    body: ProjectCreate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    _require_teacher(user)
    proj = await project_service.create_project(
        db_session,
        name=body.name,
        background_md=body.background_md,
        status=body.status,
        mainline=body.mainline,
    )
    return ProjectOut.model_validate(proj)


@router.post(
    "/internal/agent",
    response_model=AgentCaseDraftOut,
    dependencies=[Depends(require_agent_server)],
    tags=["internal-agent"],
)
async def save_agent_case_draft(
    body: AgentCaseDraftIn,
    db_session: AsyncSession = Depends(get_db),
) -> AgentCaseDraftOut:
    """Agent Server 保存 AI 生成的案例草稿（内部端点，需 X-Agent-Server-Secret）。"""
    proj, created = await project_service.save_agent_draft(
        db_session,
        project_id=body.project_id,
        name=body.name,
        background_md=body.background_md,
        objective=body.objective,
        stages=body.stages,
    )
    return AgentCaseDraftOut(
        project_id=proj.id,
        project_name=proj.name,
        stage_count=len(body.stages),
        created=created,
    )


@router.get("", response_model=Page[ProjectOut])
async def list_projects(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[ProjectOut]:
    # 学生仅可见已发布项目（草稿仅教师可见）；强制覆盖查询参数，防止 ?status=draft 绕过
    if user.role == "student":
        status = "published"
    offset = (page - 1) * page_size
    projects = await repos.list_projects(
        db_session, status=status, limit=page_size, offset=offset
    )
    total = await repos.count_projects(db_session, status=status)
    return Page(
        items=[ProjectOut.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    proj = await project_service.get_project_or_404(db_session, project_id)
    # 学生仅可查看已发布项目；draft 视为不存在（不泄露项目存在性）
    if user.role == "student" and proj.status != "published":
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    return ProjectOut.model_validate(proj)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    _require_teacher(user)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise AppError(422, "VALIDATION_ERROR", "No fields to update")
    proj = await repos.update_project(db_session, project_id, **fields)
    if not proj:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    return ProjectOut.model_validate(proj)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    _require_teacher(user)
    await project_service.get_project_or_404(db_session, project_id)
    await repos.delete_project(db_session, project_id)

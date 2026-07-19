"""Project CRUD 端点。路由只调 service + model_validate，无业务逻辑。"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.deps import get_db
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.projects import service as project_service
from tutoring.projects.schemas import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    body: ProjectCreate, db_session: AsyncSession = Depends(get_db)
) -> ProjectOut:
    proj = await project_service.create_project(
        db_session, name=body.name, background_md=body.background_md, status=body.status
    )
    return ProjectOut.model_validate(proj)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    status_filter: str | None = None,
    db_session: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    projects = await repos.list_projects(db_session, status=status_filter)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID, db_session: AsyncSession = Depends(get_db)
) -> ProjectOut:
    proj = await project_service.get_project_or_404(db_session, project_id)
    return ProjectOut.model_validate(proj)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db_session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise AppError(422, "VALIDATION_ERROR", "No fields to update")
    proj = await repos.update_project(db_session, project_id, **fields)
    if not proj:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    return ProjectOut.model_validate(proj)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, db_session: AsyncSession = Depends(get_db)
) -> None:
    await project_service.get_project_or_404(db_session, project_id)
    await repos.delete_project(db_session, project_id)

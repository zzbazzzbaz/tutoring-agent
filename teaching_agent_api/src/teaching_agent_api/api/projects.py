"""Project CRUD 端点。"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.core.deps import get_db
from teaching_agent_api.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db_session: AsyncSession = Depends(get_db)) -> ProjectOut:
    try:
        proj = await db.create_project(
            db_session,
            name=body.name,
            background_md=body.background_md,
            status=body.status,
        )
    except IntegrityError:
        await db_session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "PROJECT_NAME_CONFLICT",
                    "message": f"Project name '{body.name}' already exists",
                }
            },
        )
    return ProjectOut.model_validate(proj)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    status_filter: str | None = None,
    db_session: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    projects = await db.list_projects(db_session, status=status_filter)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, db_session: AsyncSession = Depends(get_db)) -> ProjectOut:
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
    return ProjectOut.model_validate(proj)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db_session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "No fields to update",
                }
            },
        )
    proj = await db.update_project(db_session, project_id, **fields)
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
    return ProjectOut.model_validate(proj)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db_session: AsyncSession = Depends(get_db)) -> None:
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
    await db.delete_project(db_session, project_id)

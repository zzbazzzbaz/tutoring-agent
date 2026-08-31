from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Project


async def create_project(
    db: AsyncSession,
    *,
    name: str,
    background_md: str,
    status: str = "draft",
    mainline: dict | None = None,
) -> Project:
    try:
        return await repos.create_project(
            db, name=name, background_md=background_md, status=status, mainline=mainline
        )
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            409, "PROJECT_NAME_CONFLICT", f"Project name '{name}' already exists"
        ) from exc


async def get_project_or_404(db: AsyncSession, project_id: UUID) -> Project:
    proj = await repos.get_project(db, project_id)
    if not proj:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    return proj


async def get_published_project(db: AsyncSession, project_id: UUID) -> Project:
    """确保 project 存在且已发布（开会话的前置规则）。"""
    proj = await get_project_or_404(db, project_id)
    if proj.status != "published":
        raise AppError(422, "PROJECT_NOT_PUBLISHED", "Project must be published to start a session")
    return proj

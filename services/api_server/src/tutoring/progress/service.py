# 项目学习进度--业务逻辑
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import ProjectProgress


async def update_progress(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    progress: dict,
) -> None:
    """校验项目存在后，合并写入学生进度。"""
    proj = await repos.get_project(db, project_id)
    if not proj or proj.deleted_at is not None:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    await repos.upsert_project_progress(
        db, user_id=user_id, project_id=project_id, progress=progress
    )


async def get_progress(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
) -> ProjectProgress:
    proj = await repos.get_project(db, project_id)
    if not proj or proj.deleted_at is not None:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    existing = await repos.get_project_progress(db, user_id=user_id, project_id=project_id)
    if existing is None:
        return ProjectProgress(user_id=user_id, project_id=project_id, progress={})
    return existing

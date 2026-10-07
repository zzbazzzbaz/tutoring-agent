from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Project
from tutoring.projects.schemas import AgentCaseDraftStage


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


def build_agent_mainline(objective: str, stages: list[AgentCaseDraftStage]) -> dict:
    """把 AI 输出的阶段列表规范化为 mainline 结构（id/order 由服务端生成）。"""
    normalized = []
    for index, stage in enumerate(stages, start=1):
        deliverable = None
        if stage.deliverable_title:
            deliverable = {
                "title": stage.deliverable_title,
                "instructions": stage.deliverable_instructions,
            }
        normalized.append(
            {
                "id": f"stg_{index:02d}",
                "order": index,
                "title": stage.title,
                "guide": stage.guide,
                "student_desc": stage.student_desc,
                "deliverable": deliverable,
            }
        )
    return {"objective": objective, "stages": normalized}


async def save_agent_draft(
    db: AsyncSession,
    *,
    project_id: UUID | None,
    name: str,
    background_md: str,
    objective: str,
    stages: list[AgentCaseDraftStage],
) -> tuple[Project, bool]:
    """AI 草稿保存：project_id 为空时新建；否则更新同一草稿。返回 (项目, 是否新建)。"""
    mainline = build_agent_mainline(objective, stages)
    if project_id is not None:
        proj = await repos.get_project(db, project_id)
        if not proj or proj.deleted_at is not None:
            raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
        try:
            updated = await repos.update_project(
                db, project_id, name=name, background_md=background_md, mainline=mainline
            )
        except IntegrityError as exc:
            await db.rollback()
            raise AppError(
                409, "PROJECT_NAME_CONFLICT", f"案例名称「{name}」已存在，请换一个名称"
            ) from exc
        if updated is None:
            raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
        return updated, False
    try:
        proj = await repos.create_project(
            db, name=name, background_md=background_md, status="draft", mainline=mainline
        )
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            409, "PROJECT_NAME_CONFLICT", f"案例名称「{name}」已存在，请换一个名称"
        ) from exc
    return proj, True

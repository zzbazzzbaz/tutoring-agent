"""异步 repository 函数。无类（YAGNI）。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import func

from teaching_agent_api.db.models import Project, Session, Message, Question


# === Session ===

async def create_session(
    db: AsyncSession, *, mode: str, user_id: str, project_id: UUID | None = None,
) -> Session:
    obj = Session(mode=mode, user_id=user_id, project_id=project_id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_session(db: AsyncSession, session_id: UUID) -> Session | None:
    # selectinload(Session.project) 使路由可读取 `project_name`，
    # 而不触发 lazy load（在 async 下没有 greenlet 会失败）。
    stmt = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.project))
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_sessions(
    db: AsyncSession, *, user_id: str, status: str | None = None,
    mode: str | None = None, limit: int = 20, offset: int = 0,
) -> list[Session]:
    stmt = (
        select(Session)
        .where(Session.user_id == user_id)
        .options(selectinload(Session.project))
    )
    if status:
        stmt = stmt.where(Session.status == status)
    if mode:
        stmt = stmt.where(Session.mode == mode)
    stmt = stmt.order_by(Session.last_active_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def touch_session(db: AsyncSession, session_id: UUID) -> None:
    await db.execute(
        update(Session).where(Session.id == session_id).values(last_active_at=datetime.utcnow())
    )
    await db.commit()


async def end_session(db: AsyncSession, session_id: UUID) -> None:
    await db.execute(
        update(Session).where(Session.id == session_id).values(status="ended")
    )
    await db.commit()


# === Message ===

async def save_message(db: AsyncSession, *, session_id: UUID, role: str, content: str) -> Message:
    obj = Message(session_id=session_id, role=role, content=content)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_messages(db: AsyncSession, session_id: UUID, *, limit: int = 100, offset: int = 0) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# === Question ===

async def upsert_pending_question(
    db: AsyncSession, *, session_id: UUID, topic: str, q_type: str,
    stem: str, options: list | None, answer: str, analysis: str | None,
) -> Question:
    """幂等：若 (session_id, topic) 已存在 pending 题目则返回，否则插入。"""
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing:
        return existing
    obj = Question(
        session_id=session_id, topic=topic, q_type=q_type,
        stem=stem, options=options, answer=answer, analysis=analysis,
        status="pending",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_pending_question(db: AsyncSession, session_id: UUID, topic: str) -> Question | None:
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_question(db: AsyncSession, question_id: UUID, **fields) -> None:
    fields["answered_at"] = fields.get("answered_at", datetime.utcnow())
    await db.execute(update(Question).where(Question.id == question_id).values(**fields))
    await db.commit()


async def list_questions(
    db: AsyncSession, session_id: UUID, *, status: str | None = None,
) -> list[Question]:
    stmt = select(Question).where(Question.session_id == session_id)
    if status:
        stmt = stmt.where(Question.status == status)
    stmt = stmt.order_by(Question.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# === Project ===

async def create_project(db: AsyncSession, *, name: str, background_md: str, status: str = "draft") -> Project:
    obj = Project(name=name, background_md=background_md, status=status)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_project(db: AsyncSession, project_id: UUID) -> Project | None:
    return await db.get(Project, project_id)


async def list_projects(db: AsyncSession, *, status: str | None = None) -> list[Project]:
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_project(db: AsyncSession, project_id: UUID, **fields) -> Project | None:
    await db.execute(update(Project).where(Project.id == project_id).values(**fields))
    await db.commit()
    return await db.get(Project, project_id)


async def delete_project(db: AsyncSession, project_id: UUID) -> None:
    proj = await db.get(Project, project_id)
    if proj:
        await db.delete(proj)
        await db.commit()

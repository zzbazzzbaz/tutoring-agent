"""异步 repository 函数。无类（YAGNI）。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tutoring.db.models import Project, Session, Message, Question


# === Session ===

async def create_session(
    session: AsyncSession, *, mode: str, user_id: str, project_id: UUID | None = None,
) -> Session:
    obj = Session(mode=mode, user_id=user_id, project_id=project_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_session(session: AsyncSession, session_id: UUID) -> Session | None:
    # selectinload(Session.project) 使路由可读取 `project_name`，
    # 而不触发 lazy load（在 async 下没有 greenlet 会失败）。
    stmt = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.project))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_sessions(
    session: AsyncSession, *, user_id: str, status: str | None = None,
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
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def touch_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(last_active_at=datetime.utcnow())
    )
    await session.commit()


async def end_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(status="ended")
    )
    await session.commit()


# === Message ===

async def save_message(session: AsyncSession, *, session_id: UUID, role: str, content: str) -> Message:
    obj = Message(session_id=session_id, role=role, content=content)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_messages(session: AsyncSession, session_id: UUID, *, limit: int = 100, offset: int = 0) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# === Question ===

async def upsert_pending_question(
    session: AsyncSession, *, session_id: UUID, topic: str, q_type: str,
    stem: str, options: list | None, answer: str, analysis: str | None,
) -> Question:
    """幂等：若 (session_id, topic) 已存在 pending 题目则返回，否则插入。"""
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await session.execute(stmt)
    existing = result.scalars().first()
    if existing:
        return existing
    obj = Question(
        session_id=session_id, topic=topic, q_type=q_type,
        stem=stem, options=options, answer=answer, analysis=analysis,
        status="pending",
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_pending_question(session: AsyncSession, session_id: UUID, topic: str) -> Question | None:
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def update_question(session: AsyncSession, question_id: UUID, **fields) -> None:
    fields["answered_at"] = fields.get("answered_at", datetime.utcnow())
    await session.execute(update(Question).where(Question.id == question_id).values(**fields))
    await session.commit()


async def list_questions(
    session: AsyncSession, session_id: UUID, *, status: str | None = None,
) -> list[Question]:
    stmt = select(Question).where(Question.session_id == session_id)
    if status:
        stmt = stmt.where(Question.status == status)
    stmt = stmt.order_by(Question.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# === Project ===

async def create_project(session: AsyncSession, *, name: str, background_md: str, status: str = "draft") -> Project:
    obj = Project(name=name, background_md=background_md, status=status)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def list_projects(session: AsyncSession, *, status: str | None = None) -> list[Project]:
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_project(session: AsyncSession, project_id: UUID, **fields) -> Project | None:
    await session.execute(update(Project).where(Project.id == project_id).values(**fields))
    await session.commit()
    return await session.get(Project, project_id)


async def delete_project(session: AsyncSession, project_id: UUID) -> None:
    proj = await session.get(Project, project_id)
    if proj:
        await session.delete(proj)
        await session.commit()

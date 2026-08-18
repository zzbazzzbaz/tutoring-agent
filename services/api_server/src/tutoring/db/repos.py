import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tutoring.db.models import AuthToken, Project, Session, User, Class, ClassStudent

# === User ===


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password_hash: str,
    role: str,
    name: str,
) -> User:
    obj = User(username=username, password_hash=password_hash, role=role, name=name)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_users_by_role(session: AsyncSession, role: str) -> list[User]:
    stmt = select(User).where(User.role == role).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_users_by_role(session: AsyncSession, role: str) -> int:
    stmt = select(func.count()).select_from(User).where(User.role == role)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def list_users_by_role_paginated(
    session: AsyncSession, role: str, *, limit: int, offset: int
) -> list[User]:
    stmt = (
        select(User)
        .where(User.role == role)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    obj = await session.get(User, user_id)
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False


async def update_password(session: AsyncSession, user_id: UUID, password_hash: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )
    await session.commit()


async def update_avatar_url(session: AsyncSession, user_id: UUID, avatar_url: str | None) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(avatar_url=avatar_url)
    )
    await session.commit()


# === AuthToken ===


async def create_token(session: AsyncSession, user_id: UUID) -> AuthToken:
    obj = AuthToken(token=uuid.uuid4().hex, user_id=user_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_token_with_user(session: AsyncSession, token: str) -> AuthToken | None:
    stmt = select(AuthToken).where(AuthToken.token == token).options(selectinload(AuthToken.user))
    result = await session.execute(stmt)
    return result.scalars().first()


async def delete_token(session: AsyncSession, token: str) -> bool:
    stmt = select(AuthToken).where(AuthToken.token == token)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False


# === Session ===


async def create_session(
    session: AsyncSession,
    *,
    mode: str,
    user_id: UUID,
    project_id: UUID | None = None,
) -> Session:
    obj = Session(mode=mode, user_id=user_id, project_id=project_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_session(session: AsyncSession, session_id: UUID) -> Session | None:
    stmt = select(Session).where(Session.id == session_id).options(selectinload(Session.project))
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_sessions(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    mode: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Session]:
    stmt = (
        select(Session).options(selectinload(Session.project)).where(Session.deleted_at.is_(None))
    )
    if user_id is not None:
        stmt = stmt.where(Session.user_id == user_id)
    if mode:
        stmt = stmt.where(Session.mode == mode)
    stmt = stmt.order_by(Session.last_active_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_sessions(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    mode: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Session).where(Session.deleted_at.is_(None))
    if user_id is not None:
        stmt = stmt.where(Session.user_id == user_id)
    if mode:
        stmt = stmt.where(Session.mode == mode)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def update_session_title(
    session: AsyncSession, session_id: UUID, title: str | None
) -> Session | None:
    await session.execute(update(Session).where(Session.id == session_id).values(title=title))
    await session.commit()
    return await get_session(session, session_id)


async def touch_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(last_active_at=datetime.now(UTC))
    )
    await session.commit()


async def delete_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        update(Session).where(Session.id == session_id).values(deleted_at=datetime.now(UTC))
    )
    await session.commit()


# === Project ===


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    background_md: str,
    status: str = "draft",
) -> Project:
    obj = Project(name=name, background_md=background_md, status=status)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def list_projects(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Project]:
    stmt = select(Project).where(Project.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_projects(session: AsyncSession, *, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(Project).where(Project.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Project.status == status)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def update_project(session: AsyncSession, project_id: UUID, **fields) -> Project | None:
    await session.execute(update(Project).where(Project.id == project_id).values(**fields))
    await session.commit()
    return await session.get(Project, project_id)


async def delete_project(session: AsyncSession, project_id: UUID) -> None:
    await session.execute(
        update(Project).where(Project.id == project_id).values(deleted_at=datetime.now(UTC))
    )
    await session.commit()

# === Class ===


async def create_class(
    session: AsyncSession,
    *,
    grade: str,
    classname: str,
    teacher_id: UUID,
) -> Class:
    obj = Class(grade=grade,classname=classname, teacher_id=teacher_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_class(session: AsyncSession, class_id: UUID) -> Class | None:
    stmt = select(Class).options(
        selectinload(Class.teacher),
        selectinload(Class.students).selectinload(ClassStudent.user),
    ).where(Class.id == class_id)
    result = await session.execute(stmt)
    return result.scalars().first()

# 查询班级列表（分页）
async def list_classes(
    session: AsyncSession,
    *,
    teacher_id: UUID | None = None,
    status: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Class]:
    stmt = select(Class).options(
        selectinload(Class.teacher),
        selectinload(Class.students),
    ).where(
        Class.deleted_at.is_(None)
    )
    if teacher_id is not None:
        stmt = stmt.where(Class.teacher_id == teacher_id)
    if status:
        stmt = stmt.where(Class.status == status)
    if keyword:
        stmt = stmt.where(Class.classname.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(Class.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# 统计班级总数量(前端没想好咋设计,先写上,用不上在删了)
async def count_classes(
    session: AsyncSession,
    *,
    teacher_id: UUID | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Class).where(Class.deleted_at.is_(None))
    if teacher_id is not None:
        stmt = stmt.where(Class.teacher_id == teacher_id)
    if status:
        stmt = stmt.where(Class.status == status)
    if keyword:
        stmt = stmt.where(Class.classname.ilike(f"%{keyword}%"))
    result = await session.execute(stmt)
    return int(result.scalar_one())

# 更新班级表信息
async def update_class(
    session: AsyncSession, class_id: UUID, **fields
) -> Class | None:
    await session.execute(
        update(Class).where(Class.id == class_id).values(**fields)
    )
    await session.commit()
    return await session.get(Class, class_id)

# 软删除
async def delete_class(session: AsyncSession, class_id: UUID) -> None:
    await session.execute(
        update(Class)
        .where(Class.id == class_id)
        .values(deleted_at=datetime.now(UTC))
    )
    await session.commit()

# 新增班级学生
async def add_students_to_class(
    session: AsyncSession, class_id: UUID, user_ids: list[UUID]
) -> int:
    """批量添加学生到班级，返回实际添加数（忽略已存在的）。"""
    existing = select(ClassStudent.user_id).where(
        ClassStudent.class_id == class_id,
        ClassStudent.user_id.in_(user_ids),
    )
    result = await session.execute(existing)
    existing_ids = set(result.scalars().all())

    count = 0
    for uid in user_ids:
        if uid in existing_ids:
            continue
        obj = ClassStudent(class_id=class_id, user_id=uid)
        session.add(obj)
        count += 1
    if count > 0:
        await session.commit()
    return count

# 物理删除班级学生
async def remove_student_from_class(
    session: AsyncSession, class_id: UUID, user_id: UUID
) -> None:
    stmt = select(ClassStudent).where(
        ClassStudent.class_id == class_id, ClassStudent.user_id == user_id
    )
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj:
        await session.delete(obj)
        await session.commit()

# 批量删除班级学生
async def bulk_remove_students_from_class(
    session: AsyncSession, class_id: UUID, user_ids: list[UUID]
) -> int:
    stmt = select(ClassStudent).where(
        ClassStudent.class_id == class_id,
        ClassStudent.user_id.in_(user_ids),
    )
    result = await session.execute(stmt)
    objs = list(result.scalars().all())
    for obj in objs:
        await session.delete(obj)
    await session.commit()
    return len(objs)

# 查询班级下学生列表（分页）
async def list_class_students(
    session: AsyncSession,
    class_id: UUID,
    *,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ClassStudent]:
    stmt = (
        select(ClassStudent)
        .options(selectinload(ClassStudent.user))
        .where(ClassStudent.class_id == class_id)
    )
    if keyword:
        stmt = stmt.join(User).where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    stmt = stmt.order_by(ClassStudent.joined_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# 统计班级学生数量
async def count_class_students(
    session: AsyncSession,
    class_id: UUID,
    *,
    keyword: str | None = None,
) -> int:
    base = select(func.count()).select_from(ClassStudent).where(
        ClassStudent.class_id == class_id
    )
    if keyword:
        base = base.join(User).where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    result = await session.execute(base)
    return int(result.scalar_one())

# 判断某个用户是否是班级成员
async def check_class_member(
    session: AsyncSession, class_id: UUID, user_id: UUID
) -> bool:
    stmt = select(func.count()).select_from(ClassStudent).where(
        ClassStudent.class_id == class_id,
        ClassStudent.user_id == user_id,
    )
    result = await session.execute(stmt)
    return int(result.scalar_one()) > 0

# 学生会话统计
async def count_class_sessions(
    session: AsyncSession,
    class_id: UUID,
    *,
    mode: str | None = None,
) -> int:
    base = (
        select(func.count())
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id == class_id,
            Session.deleted_at.is_(None),
        )
    )
    if mode:
        base = base.where(Session.mode == mode)
    result = await session.execute(base)
    return int(result.scalar_one())

# 班级统计
async def get_class_stats(
    session: AsyncSession,
    class_id: UUID,
) -> dict:
    """班级统计概览。"""
    total_students = await count_class_students(session, class_id)
    total_sessions = await count_class_sessions(session, class_id)

    # 今日活跃学生数（今天有会话活动的学生）
    today = datetime.now(UTC).date()
    active_stmt = (
        select(func.count(func.distinct(Session.user_id)))
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id == class_id,
            Session.deleted_at.is_(None),
            func.date(Session.last_active_at) == today,
        )
    )
    active_result = await session.execute(active_stmt)
    active_today = int(active_result.scalar_one())

    return {
        "total_students": total_students,
        "total_sessions": total_sessions,
        "active_today": active_today,
    }

# 班级项目关联(班级是否关联项目进行查询.待定,如果展示则class表要添加project_id字段,在新增对应函数)
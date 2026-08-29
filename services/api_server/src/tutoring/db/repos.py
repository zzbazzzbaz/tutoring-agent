import uuid
from datetime import UTC, datetime,date, timedelta
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


""" async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    obj = await session.get(User, user_id)
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False """


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

# 软删除用户
async def soft_delete_users(
    session: AsyncSession, user_ids: list[UUID], *, reason: str, deleted_by: UUID
) -> int:
    stmt = (
        update(User)
        .where(User.id.in_(user_ids), User.deleted_at.is_(None))
        .values(
            deleted_at=datetime.now(UTC),
            deleted_reason=reason,
            deleted_by=deleted_by,
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


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

# 创建班级
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

# 查询班级信息
async def get_class(session: AsyncSession, class_id: UUID) -> Class | None:
    stmt = select(Class).options(
        selectinload(Class.teacher),
        selectinload(Class.students).selectinload(ClassStudent.user),
    ).where(Class.id == class_id, Class.deleted_at.is_(None))
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

# 统计班级总数量
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

# === Student ===
# 统计未分配班级的学生数量
async def count_unassigned_students(session: AsyncSession, keyword: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .outerjoin(ClassStudent, ClassStudent.user_id == User.id)
        .where(User.role == "student", ClassStudent.user_id.is_(None))
    )
    if keyword:
        stmt = stmt.where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())

# 查询未分配班级的学生列表（分页）
async def list_unassigned_students(
    session: AsyncSession, *, limit: int, offset: int, keyword: str | None = None
) -> list[User]:
    stmt = (
        select(User)
        .outerjoin(ClassStudent, ClassStudent.user_id == User.id)
        .where(User.role == "student", ClassStudent.user_id.is_(None))
    )
    if keyword:
        stmt = stmt.where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# 手动新增班级学生
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
    class_id: UUID| list[UUID],
    *,
    keyword: str | None = None,
) -> int:
    # 统一转为列表处理
    class_ids = class_id if isinstance(class_id, list) else [class_id]
    base = select(func.count()).select_from(ClassStudent).where(
        ClassStudent.class_id.in_(class_ids)
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

# 查询班级下会话列表（分页）
async def list_class_sessions(
    session: AsyncSession,
    class_id: UUID| list[UUID],
    *,
    mode: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
)->list[Session]:
    class_ids = class_id if isinstance(class_id,list) else [class_id]
    stmt = (
        select(Session)
        .options(selectinload(Session.project),selectinload(Session.user))
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .join(User, User.id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
        )
    )
    if mode:
        stmt = stmt.where(Session.mode == mode)
    if keyword:
        stmt = stmt.where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    stmt = stmt.order_by(Session.last_active_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# 班级会话统计(支持单班级或多班级,支持日期过滤)
async def count_class_sessions(
    session: AsyncSession,
    class_id: UUID| list[UUID],
    *,
    mode: str | None = None,
    since: date | None = None,
    keyword: str | None = None,
) -> int:
    class_ids = class_id if isinstance(class_id, list) else [class_id]
    base = (
        select(func.count())
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
        )
    )
    if mode:
        base = base.where(Session.mode == mode)
    if since:
        base = base.where(func.date(Session.last_active_at) >= since)
    if keyword:
        base = base.join(User, User.id == Session.user_id).where(
            (User.name.ilike(f"%{keyword}%")) | (User.username.ilike(f"%{keyword}%"))
        )
    result = await session.execute(base)
    return int(result.scalar_one())

# 班级统计（支持单/多班级）
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

# === 统计分析--学情总览 Analytics (Dashboard) ===

async def list_classes_by_teacher(
    session: AsyncSession,
    teacher_id: UUID,
) -> list[Class]:
    """获取某教师的所有活跃班级。"""
    stmt = (
        select(Class)
        .where(
            Class.teacher_id == teacher_id,
            Class.deleted_at.is_(None),
        )
        .order_by(Class.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def count_active_students_in_classes(
    session: AsyncSession,
    class_ids: list[UUID],
    target_date: date,
) -> int:
    """统计指定日期有会话活动的学生数（去重）。"""
    stmt = (
        select(func.count(func.distinct(Session.user_id)))
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            func.date(Session.last_active_at) == target_date,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())

async def list_anomaly_students(
    session: AsyncSession,
    class_ids: list[UUID],
    inactive_threshold_days: int = 7,
) -> list[dict]:
    """
    列出未活跃超过阈值天数的学生。
    """
    threshold_dt = datetime.now(UTC) - timedelta(days=inactive_threshold_days)

    # 查询所有班级学生及其最后活跃时间
    students_stmt = (
        select(ClassStudent, User, Class)
        .join(User, User.id == ClassStudent.user_id)
        .join(Class, Class.id == ClassStudent.class_id)
        .where(ClassStudent.class_id.in_(class_ids))
    )
    result = await session.execute(students_stmt)
    all_rows = result.all()

    anomalies = []
    for cs, user, cls in all_rows:
        # 获取该学生最近一次会话活动时间
        last_active_stmt = (
            select(func.max(Session.last_active_at))
            .select_from(Session)
            .where(
                Session.user_id == user.id,
                Session.deleted_at.is_(None),
            )
        )
        last_active = (await session.execute(last_active_stmt)).scalar_one_or_none()

        if last_active is None:
            # 从未有过会话记录
            inactive_days = 999
            last_active_display = None
        else:
            delta = datetime.now(UTC) - last_active
            inactive_days = delta.days
            last_active_display = last_active

        if inactive_days >= inactive_threshold_days:
            anomalies.append({
                "user_id": user.id,
                "name": user.name,
                "username": user.username,
                "last_active_at": last_active_display,
                "inactive_days": inactive_days,
                "alert_type": "inactive",
                "class_id": cls.id,
                "class_name": f"{cls.grade} {cls.classname}",
            })
    # 按未活跃天数降序排列
    anomalies.sort(key=lambda x: x["inactive_days"], reverse=True)
    return anomalies

# 学习趋势
async def get_daily_trend(
    session: AsyncSession,
    class_ids: list[UUID],
    days: int = 30,
) -> list[dict]:
    """
    获取最近 N 天每天的对话数和活跃学生数。
    """
    today = datetime.now(UTC).date()
    trend = []

    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        next_date = target_date + timedelta(days=1)
        # 当日对话数
        session_stmt = (
            select(func.count())
            .select_from(Session)
            .join(ClassStudent, ClassStudent.user_id == Session.user_id)
            .where(
                ClassStudent.class_id.in_(class_ids),
                Session.deleted_at.is_(None),
                func.date(Session.last_active_at) >= target_date,
                func.date(Session.last_active_at) < next_date,
            )
        )
        session_count = int((await session.execute(session_stmt)).scalar_one())
        # 当日活跃学生数
        active_stmt = (
            select(func.count(func.distinct(Session.user_id)))
            .select_from(Session)
            .join(ClassStudent, ClassStudent.user_id == Session.user_id)
            .where(
                ClassStudent.class_id.in_(class_ids),
                Session.deleted_at.is_(None),
                func.date(Session.last_active_at) >= target_date,
                func.date(Session.last_active_at) < next_date,
            )
        )
        active_count = int((await session.execute(active_stmt)).scalar_one())

        trend.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "session_count": session_count,
            "active_student_count": active_count,
        })

    return trend


async def get_class_comparison(
    session: AsyncSession,
    classes: list[Class],
) -> list[dict]:
    """
    班级间活跃率对比。
    """
    today = datetime.now(UTC).date()
    comparison = []

    for cls in classes:
        # 该班级学生总数
        total_stmt = (
            select(func.count())
            .select_from(ClassStudent)
            .where(ClassStudent.class_id == cls.id)
        )
        total = int((await session.execute(total_stmt)).scalar_one())
        # 该班级今日活跃学生数
        active_stmt = (
            select(func.count(func.distinct(Session.user_id)))
            .select_from(Session)
            .join(ClassStudent, ClassStudent.user_id == Session.user_id)
            .where(
                ClassStudent.class_id == cls.id,
                Session.deleted_at.is_(None),
                func.date(Session.last_active_at) == today,
            )
        )
        active = int((await session.execute(active_stmt)).scalar_one())
        rate = round(active / total, 2) if total > 0 else 0.0

        comparison.append({
            "class_id": cls.id,
            "class_name": f"{cls.grade} {cls.classname}",
            "total_students": total,
            "active_today": active,
            "active_rate": rate,
        })

    return comparison

# === 统计分析--学生分析 Student Analysis ===

async def get_student_learning_data(
    session: AsyncSession,
    user_id: UUID,
    class_ids: list[UUID] | None = None,
) -> dict:
    """
    获取学生的基本学习数据：总对话数、总活跃天数、最后活跃时间。
    如果指定 class_ids 则只统计该班级范围内的数据。
    """
    # 总对话数
    sessions_stmt = (
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user_id, Session.deleted_at.is_(None))
    )
    if class_ids:
        sessions_stmt = sessions_stmt.join(
            ClassStudent, ClassStudent.user_id == Session.user_id
        ).where(ClassStudent.class_id.in_(class_ids))
    total_sessions = int((await session.execute(sessions_stmt)).scalar_one())

    # 最后活跃时间
    last_active_stmt = (
        select(func.max(Session.last_active_at))
        .select_from(Session)
        .where(Session.user_id == user_id, Session.deleted_at.is_(None))
    )
    last_active = (await session.execute(last_active_stmt)).scalar_one_or_none()

    # 活跃天数（有对话记录的不同日期数）
    active_days_stmt = (
        select(func.count(func.distinct(func.date(Session.last_active_at))))
        .select_from(Session)
        .where(Session.user_id == user_id, Session.deleted_at.is_(None))
    )
    if class_ids:
        active_days_stmt = active_days_stmt.join(
            ClassStudent, ClassStudent.user_id == Session.user_id
        ).where(ClassStudent.class_id.in_(class_ids))
    active_days = int((await session.execute(active_days_stmt)).scalar_one())

    return {
        "total_sessions": total_sessions,
        "last_active_at": last_active,
        "active_days": active_days,
    }
# 按学生查对话数
async def count_student_sessions_since(
    session: AsyncSession,
    user_id: UUID,
    since: date,
) -> int:
    """统计学生在指定日期之后(含)的对话数。
        最近7天对话数（今天+前6天）
    """
    stmt = (
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id == user_id,
            Session.deleted_at.is_(None),
            func.date(Session.last_active_at) >= since,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())

async def get_student_daily_activity(
    session: AsyncSession,
    user_id: UUID,
    days: int = 30,
) -> list[dict]:
    """获取学生最近N天每天的对话数。"""
    today = datetime.now(UTC).date()
    activity = []

    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        next_date = target_date + timedelta(days=1)

        stmt = (
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id == user_id,
                Session.deleted_at.is_(None),
                func.date(Session.last_active_at) >= target_date,
                func.date(Session.last_active_at) < next_date,
            )
        )
        count = int((await session.execute(stmt)).scalar_one())
        activity.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "session_count": count,
        })

    return activity

async def get_student_classes(
    session: AsyncSession,
    user_id: UUID,
) -> list[dict]:
    """获取学生所属的所有班级。"""
    stmt = (
        select(ClassStudent, Class)
        .join(Class, Class.id == ClassStudent.class_id)
        .where(
            ClassStudent.user_id == user_id,
            Class.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "class_id": cls.id,
            "class_name": f"{cls.grade} {cls.classname}",
            "joined_at": cs.joined_at,
        }
        for cs, cls in rows
    ]
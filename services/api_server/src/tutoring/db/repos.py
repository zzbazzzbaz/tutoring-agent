import uuid
from datetime import UTC, datetime,date, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tutoring.db.models import (
    AuthToken,
    Class,
    ClassStudent,
    Message,
    Project,
    Session,
    SessionProgress,
    User,
)

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
    mainline: dict | None = None,
) -> Project:
    obj = Project(name=name, background_md=background_md, status=status, mainline=mainline)
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


# === SessionProgress ===


async def upsert_session_progress(
    session: AsyncSession,
    *,
    session_id: UUID,
    progress: dict,
) -> SessionProgress:
    """写入/更新某会话的学习进度（合并式更新：仅覆盖传入的 stage_id）。"""
    existing = await get_session_progress(session, session_id=session_id)
    merged: dict = {**(existing.progress if existing else {}), **progress}
    if existing:
        existing.progress = merged
        existing.updated_at = datetime.now(UTC)
        obj = existing
    else:
        obj = SessionProgress(session_id=session_id, progress=merged)
        session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_session_progress(
    session: AsyncSession,
    *,
    session_id: UUID,
) -> SessionProgress | None:
    return await session.get(SessionProgress, session_id)


# === 项目维度进度聚合（报告「阶段分布/产出物完成」） ===

# 阶段状态等级：pending < in_progress < completed
_STATUS_RANK = {"pending": 0, "in_progress": 1, "completed": 2}


def _merge_stage_progress(existing: dict | None, incoming: dict) -> dict:
    """合并同一 (学生, 项目, 阶段) 的两条进度记录。

    - status 取状态最高值（pending < in_progress < completed）
    - deliverable_done 取任一 True
    - deliverable 内容：优先保留已达标者的；都未达标时保留后写入的
    """
    merged = dict(incoming)
    if existing:
        if _STATUS_RANK.get(existing.get("status"), 0) > _STATUS_RANK.get(
            merged.get("status"), 0
        ):
            merged["status"] = existing["status"]
        if bool(existing.get("deliverable_done")) and not bool(merged.get("deliverable_done")):
            merged["deliverable_done"] = True
            if existing.get("deliverable"):
                merged["deliverable"] = existing["deliverable"]
    return merged


async def list_project_progress_summary(
    session: AsyncSession,
    *,
    class_ids: list[UUID],
) -> list[dict]:
    """项目维度进度聚合：班级范围内每个项目的阶段分布 + 产出物完成。

    聚合口径（报告「阶段分布/产出物完成」板块用，注意与消息级统计区分）：
    - 项目范围：**全量 published 项目**（含 0 会话、0 进度的项目，计数为 0），
      不随班级内会话有无而增减（方案 B：教师一眼能看到尚未启动的项目）。
    - 统计单元 = 学生 × 项目：同一学生同一项目多个会话的进度合并，
      每个 stage 取状态最高值；产出物取"已达标优先、否则后写入"。
    - 时间窗口：不限（进度是跨会话累积的当前状态，不随报告天数切换变化）。
    - 会话范围：班级学生（class_student）名下、未删除的 project 模式会话。
    - 分母（student_count）：该项目下有 project 模式会话的学生数（去重）；
      "参与"以会话为准，与学生是否上报过阶段进度（SessionProgress）无关。
    """
    # 1. 全量 published 项目（mainline 阶段定义来源，先取项目再按会话聚合）
    projects_stmt = (
        select(Project)
        .where(
            Project.status == "published",
            Project.deleted_at.is_(None),
        )
        .order_by(Project.name)
    )
    projects = (await session.execute(projects_stmt)).scalars().all()
    if not projects:
        return []

    # 2. 班级范围内的 project 模式会话（可为 0 条：全量列出项目时允许 0 会话）
    sessions_stmt = (
        select(Session.id, Session.user_id, Session.project_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.mode == "project",
            Session.project_id.is_not(None),
            Session.deleted_at.is_(None),
        )
    )
    session_rows = (await session.execute(sessions_stmt)).all()

    user_by_session: dict[UUID, UUID] = {}
    project_by_session: dict[UUID, UUID] = {}
    session_ids: list[UUID] = []
    # 参与学生按 (项目) 去重：有 project 模式会话即视为参与，与是否有进度记录无关
    students_by_project: dict[UUID, set[UUID]] = {}
    for sid, uid, pid in session_rows:
        user_by_session[sid] = uid
        project_by_session[sid] = pid
        session_ids.append(sid)
        students_by_project.setdefault(pid, set()).add(uid)

    # 3. 会话进度 + 按 (学生, 项目) 合并会话进度
    merged: dict[tuple[UUID, UUID], dict[str, dict]] = {}
    if session_rows:
        progress_stmt = select(SessionProgress).where(SessionProgress.session_id.in_(session_ids))
        progress_rows = (await session.execute(progress_stmt)).scalars().all()
        for sp in progress_rows:
            sid = sp.session_id
            key = (user_by_session.get(sid), project_by_session.get(sid))
            if None in key:
                continue
            per_stage = merged.setdefault(key, {})
            for stage_id, stage_prog in (sp.progress or {}).items():
                per_stage[stage_id] = _merge_stage_progress(
                    per_stage.get(stage_id), dict(stage_prog)
                )

    # 4. 输出每个项目的阶段统计（projects 已按 name 排序）
    results: list[dict] = []
    for proj in projects:
        mainline = proj.mainline or {}
        stages_def = mainline.get("stages") or []
        student_count = len(students_by_project.get(proj.id, set()))

        stage_stats: list[dict] = []
        for sd in stages_def:
            stage_id = sd.get("id")
            deliverable_def = (
                sd.get("deliverable") if isinstance(sd.get("deliverable"), dict) else None
            )
            stats = {
                "stage_id": sd.get("id"),
                "order": sd.get("order"),
                "title": sd.get("title"),
                "has_deliverable": bool(deliverable_def),
                "deliverable_title": (deliverable_def or {}).get("title"),
                "completed_count": 0,
                "in_progress_count": 0,
                "started_count": 0,
                "deliverable_submitted_count": 0,
                "deliverable_done_count": 0,
            }
            for (uid, pid), per_stage in merged.items():
                if pid != proj.id:
                    continue
                st = per_stage.get(stage_id)
                if not st:
                    continue
                status = st.get("status")
                if status == "completed":
                    stats["completed_count"] += 1
                elif status == "in_progress":
                    stats["in_progress_count"] += 1
                if status in ("in_progress", "completed"):
                    stats["started_count"] += 1
                if st.get("deliverable"):
                    stats["deliverable_submitted_count"] += 1
                if st.get("deliverable_done"):
                    stats["deliverable_done_count"] += 1
            stage_stats.append(stats)

        results.append(
            {
                "project_id": proj.id,
                "project_name": proj.name,
                "student_count": student_count,
                "stage_count": len(stages_def),
                "stages": stage_stats,
            }
        )
    return results

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
    return await get_class(session, class_id)

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
        .join(User, User.id == ClassStudent.user_id)
        .where(
            ClassStudent.class_id == class_id,
            User.deleted_at.is_(None),  # 排除已软删学生
        )
    )
    if keyword:
        stmt = stmt.where(
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
    # 多班学生按 user_id 去重计数，避免跨班重复统计（如学生同时在多班） 
    base = (
        select(func.count(func.distinct(ClassStudent.user_id)))
        .select_from(ClassStudent)
        .join(User, User.id == ClassStudent.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),# 排除已软删学生
        )
    )
    if keyword:
        base = base.where(
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
            User.deleted_at.is_(None),  # 排除已软删学生的会话
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
    # 先取班级范围内【去重后】的学生集合，再按 user_id 直接计数；
    class_student_subq = (
        select(ClassStudent.user_id)
        .join(User, User.id == ClassStudent.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),# 排除已软删学生
        )
        .distinct()
    )
    base = (
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id.in_(class_student_subq),
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
        .join(User, User.id == Session.user_id)
        .where(
            ClassStudent.class_id == class_id,
            User.deleted_at.is_(None),  # 排除已软删学生
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
    """获取某教师的所有活跃班级（排除归档班级，归档班不参与统计聚合）。"""
    stmt = (
        select(Class)
        .where(
            Class.teacher_id == teacher_id,
            Class.deleted_at.is_(None),
            Class.status == "active",
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
        .join(User, User.id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),  # 排除已软删学生
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
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),  # 排除已软删学生
        )
    )
    result = await session.execute(students_stmt)
    all_rows = result.all()

    # 按 user_id 去重，多班学生只出现一次（inactive_days 按学生整体计算，
    # 与班级无关，任取一条即可，避免待关注列表重复）
    anomalies_by_user: dict[UUID, dict] = {}
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

        if inactive_days >= inactive_threshold_days and user.id not in anomalies_by_user:
            anomalies_by_user[user.id] = {
                "user_id": user.id,
                "name": user.name,
                "username": user.username,
                "last_active_at": last_active_display,
                "inactive_days": inactive_days,
                "alert_type": "inactive",
                "class_id": cls.id,
                "class_name": f"{cls.grade} {cls.classname}",
            }
    # 按未活跃天数降序排列
    anomalies = sorted(
        anomalies_by_user.values(),
        key=lambda x: x["inactive_days"],
        reverse=True,
    )
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
    # 班级范围内去重后的学生集合，会话按 user_id 直接计数避免多班翻倍
    class_student_subq = (
        select(ClassStudent.user_id)
        .join(User, User.id == ClassStudent.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),# 排除已软删学生
        )
        .distinct()
    )

    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        next_date = target_date + timedelta(days=1)
        # 当日对话数
        session_stmt = (
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id.in_(class_student_subq),
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
            .join(User, User.id == Session.user_id)
            .where(
                ClassStudent.class_id.in_(class_ids),
                User.deleted_at.is_(None),  # 排除已软删学生
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
        # 该班级学生总数（排除已软删学生）
        total_stmt = (
            select(func.count())
            .select_from(ClassStudent)
            .join(User, User.id == ClassStudent.user_id)
            .where(
                ClassStudent.class_id == cls.id,
                User.deleted_at.is_(None),
            )
        )
        total = int((await session.execute(total_stmt)).scalar_one())
        # 该班级今日活跃学生数（排除已软删学生）
        active_stmt = (
            select(func.count(func.distinct(Session.user_id)))
            .select_from(Session)
            .join(ClassStudent, ClassStudent.user_id == Session.user_id)
            .join(User, User.id == Session.user_id)
            .where(
                ClassStudent.class_id == cls.id,
                User.deleted_at.is_(None),
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
    先校验该生属于 class_ids 中任一班级，属于则按 user_id 直接统计。
    """
    if class_ids:
        is_member = False
        for cid in class_ids:
            if await check_class_member(session, cid, user_id):
                is_member = True
                break
        if not is_member:
            return {"total_sessions": 0, "last_active_at": None, "active_days": 0}

    # 总对话数（会话归属学生个人，按 user_id 直接统计）
    sessions_stmt = (
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user_id, Session.deleted_at.is_(None))
    )
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
    active_days = int((await session.execute(active_days_stmt)).scalar_one())

    return {
        "total_sessions": total_sessions,
        "last_active_at": last_active,
        "active_days": active_days,
    }

async def list_student_activity_ranking(
    session: AsyncSession,
    class_ids: list[UUID] | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    按学生统计累计对话数和活跃天数，按对话数降序排列。
    如果指定 class_ids 则只统计这些班级下的学生（用子查询避免 JOIN 重复计数）。
    """
    stmt = (
        select(
            Session.user_id,
            User.name,
            User.username,
            func.count(Session.id).label("total_sessions"),
            func.count(func.distinct(func.date(Session.last_active_at))).label("active_days"),
            func.max(Session.last_active_at).label("last_active_at"),
        )
        .join(User, User.id == Session.user_id)
        .where(Session.deleted_at.is_(None))
        .group_by(Session.user_id, User.name, User.username)
        .order_by(func.count(Session.id).desc())
        .limit(limit)
    )
    if class_ids:
        class_student_subq = (
            select(ClassStudent.user_id)
            .join(User, User.id == ClassStudent.user_id)
            .where(
                ClassStudent.class_id.in_(class_ids),
                User.deleted_at.is_(None),  # 排除已软删学生
            )
            .distinct()
        )
        stmt = stmt.where(Session.user_id.in_(class_student_subq))

    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.all()]

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
# === Message ===

async def create_messages(
    session: AsyncSession,
    *,
    session_id: UUID,
    items: list[dict],
) -> int:
    """批量写入消息记录。items: [{role, content, knowledge_hit, knowledge_doc_ids}]。返回写入条数。"""
    for item in items:
        session.add(
            Message(
                session_id=session_id,
                role=item["role"],
                content=item["content"],
                knowledge_hit=bool(item.get("knowledge_hit", False)),
                knowledge_doc_ids=list(item.get("knowledge_doc_ids") or []),
            )
        )
    await session.commit()
    return len(items)


async def get_message_stats(
    session: AsyncSession,
    class_ids: list[UUID],
    since: date,
) -> dict:
    """统计班级范围内、`since`（含）起的消息级互动指标。

    口径（互动明细/知识命中率用，注意与会话级统计区分）：
    - 总互动 = 窗口内全部消息数（学生发起 + AI 回复）
    - 学生发起 = role=student 的消息数
    - AI 回复 = role=assistant 的消息数
    - 知识命中数 = role=student 且 knowledge_hit=True 的消息数
    时间过滤按 Message.created_at 的自然日（>= since）；冷启动期无消息时各计数为 0。
    """
    stmt = (
        select(
            func.count(Message.id).label("total"),# 总互动
            func.sum(case((Message.role == "student", 1), else_=0)).label("student_count"),# 学生发起
            func.sum(case((Message.role == "assistant", 1), else_=0)).label("assistant_count"),# AI 回复
            func.sum(case((Message.knowledge_hit.is_(True), 1), else_=0)).label("hit_count"),# 知识命中数
        )
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)# 消息→会话
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)# 会话→班级学生
        .where(
            ClassStudent.class_id.in_(class_ids),# 只算当前班级范围
            Session.deleted_at.is_(None),# 排除已删会话
            func.date(Message.created_at) >= since,# 只算时间窗口内
        )
    )
    result = await session.execute(stmt)
    row = result.one()
    return {
        "total_messages": int(row.total or 0),
        "student_messages": int(row.student_count or 0),
        "assistant_messages": int(row.assistant_count or 0),
        "knowledge_hit_count": int(row.hit_count or 0),
    }


async def count_sessions_in_window(
    session: AsyncSession,
    class_ids: list[UUID],
    since: date,
) -> int:
    """统计窗口内（Message.created_at >= since）产生过消息的会话数（平均轮次分母，去重）。

    冷启动期历史会话无消息数据，不会被计入该分母，避免稀释平均轮次。
    """
    stmt = (
        select(func.count(func.distinct(Message.session_id)))
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            func.date(Message.created_at) >= since,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def get_class_participation_stats(
    session: AsyncSession,
    *,
    class_ids: list[UUID],
    since: date,
) -> dict:
    """班级参与度统计（「参与度」维度的数据源）。

    口径（窗口 = 报告 7/30 天自然日，随班级选择联动）：
    - total_students：班级学生总数（去重）
    - active_students：窗口内有过未删除会话的学生数（去重，会话按 last_active_at）
    - sessions：窗口内会话数（按 Session.last_active_at 自然日）
    - active_days：窗口内有会话的自然日天数（去重）
    - student_messages：窗口内学生发起消息数（按 Message.created_at 自然日，
      message 表自启用后累积，冷启动期可能为 0）
    """
    # 1. 学生总数（班级去重）
    total_stmt = (
        select(func.count(func.distinct(ClassStudent.user_id)))
        .select_from(ClassStudent)
        .where(ClassStudent.class_id.in_(class_ids))
    )
    total_students = int((await session.execute(total_stmt)).scalar_one())

    # 2. 活跃学生数 / 会话数 / 活跃天数（同一会话范围一次查出）
    act_stmt = (
        select(
            func.count(func.distinct(Session.user_id)).label("active_students"),
            func.count(Session.id).label("sessions"),
            func.count(func.distinct(func.date(Session.last_active_at))).label("active_days"),
        )
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            func.date(Session.last_active_at) >= since,
        )
    )
    act_row = (await session.execute(act_stmt)).one()

    # 3. 学生发起消息数（message 表）
    student_messages = (await get_message_stats(session, class_ids, since=since))[
        "student_messages"
    ]

    return {
        "total_students": total_students,
        "active_students": int(act_row.active_students),
        "sessions": int(act_row.sessions),
        "active_days": int(act_row.active_days),
        "student_messages": student_messages,
    }


# 思考质量：提问深度关键词（命中任一词即算深度提问）
_THINKING_DEPTH_PATTERN = (
    "(为什么|如何|怎样|怎么|哪些|如果|是否|原因|机制|原理|"
    "影响|比较|区别|联系|分析|解释|结合|依据)"
)


async def get_class_thinking_stats(
    session: AsyncSession,
    *,
    class_ids: list[UUID],
    since: date,
) -> dict:
    """班级思考质量统计（「思考质量」维度的数据源，规则化代理指标）。

    口径（窗口 = 报告 7/30 天自然日，随班级选择联动；基于 message 表）：
    - student_messages：窗口内学生提问总数（role=student）
    - deep_questions：含深度词（_THINKING_DEPTH_PATTERN）的学生提问数
    - follow_up_messages：非会话首条的学生消息数（AI 回复后继续提问，主动追问）
    - knowledge_hit_count：命中知识库的学生提问数（复用互动明细口径）
    - assistant_messages：窗口内 AI 回复数
    - sessions_with_messages：窗口内产生过消息的会话数（平均轮次分母，去重）
    冷启动期 message 表无数据时各计数为 0。
    """
    # 1. 消息级聚合（学生/助手消息、深度提问、知识命中，一次查出）
    main_stmt = (
        select(
            func.count(Message.id).label("total"),
            func.sum(case((Message.role == "student", 1), else_=0)).label("student_messages"),
            func.sum(case((Message.role == "assistant", 1), else_=0)).label("assistant_messages"),
            func.sum(
                case(
                    (and_(Message.role == "student", Message.knowledge_hit.is_(True)), 1),
                    else_=0,
                )
            ).label("hit_count"),
            func.sum(
                case(
                    (
                        and_(
                            Message.role == "student",
                            Message.content.op("~*")(_THINKING_DEPTH_PATTERN),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("deep_count"),
        )
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            func.date(Message.created_at) >= since,
        )
    )
    main_row = (await session.execute(main_stmt)).one()

    # 2. 主动追问：非会话首条的学生消息（窗口函数 row_number，rn>1）
    rn = func.row_number().over(
        partition_by=Message.session_id,
        order_by=Message.created_at,
    ).label("rn")
    follow_subq = (
        select(Message.id.label("mid"), rn)
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            Message.role == "student",
            func.date(Message.created_at) >= since,
        )
        .subquery()
    )
    follow_stmt = select(func.count()).select_from(follow_subq).where(follow_subq.c.rn > 1)
    follow_up = int((await session.execute(follow_stmt)).scalar_one())

    # 3. 有消息会话数（平均轮次分母，去重）
    sessions_with_messages = await count_sessions_in_window(session, class_ids, since)

    return {
        "student_messages": int(main_row.student_messages or 0),
        "deep_questions": int(main_row.deep_count or 0),
        "follow_up_messages": follow_up,
        "knowledge_hit_count": int(main_row.hit_count or 0),
        "assistant_messages": int(main_row.assistant_messages or 0),
        "sessions_with_messages": sessions_with_messages,
    }


async def get_class_subject_stats(
    session: AsyncSession,
    *,
    class_ids: list[UUID],
    since: date,
) -> dict:
    """班级学科维度统计（「学科维度」维度的数据源，规则化代理指标）。

    口径（窗口 = 报告 7/30 天自然日；范围 = 班级内**项目模式会话**，与文档
    "项目全体会话命中去重文档数"一致；基于 message.knowledge_doc_ids，
    起落库累积，冷启动期为空）：
    - project_students：窗口内项目模式会话学生数（去重，人均分母，"有会话即参与"）
    - student_doc_counts：窗口内每学生命中的去重文档数（仅命中>0 的学生，{user_id: count}）
    - class_doc_count：全班项目模式会话命中去重文档总数（分母，去重）
    """
    # 1. 参与项目学生数（窗口内项目模式会话，按 last_active_at，与参与度口径一致）
    students_stmt = (
        select(func.count(func.distinct(Session.user_id)))
        .select_from(Session)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.mode == "project",
            Session.deleted_at.is_(None),
            func.date(Session.last_active_at) >= since,
        )
    )
    project_students = int((await session.execute(students_stmt)).scalar_one())

    # 2. 每学生命中去重文档数（项目模式会话 + 窗口 + 仅 student 消息）
    #    jsonb 数组展开用 FROM 子句（LATERAL），聚合内不能直接调用 set-returning 函数
    doc_series = (
        func.jsonb_array_elements_text(Message.knowledge_doc_ids)
        .table_valued("doc")
        .render_derived(name="d")
    )
    per_student_stmt = (
        select(
            Session.user_id.label("uid"),
            func.count(func.distinct(doc_series.c.doc)).label("doc_cnt"),
        )
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .join(doc_series, true())
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.mode == "project",
            Session.deleted_at.is_(None),
            Message.role == "student",
            func.date(Message.created_at) >= since,
        )
        .group_by(Session.user_id)
    )
    student_doc_counts: dict[str, int] = {}
    for row in (await session.execute(per_student_stmt)).all():
        student_doc_counts[str(row.uid)] = int(row.doc_cnt)

    # 3. 全班命中去重文档总数（同范围，去重）
    class_stmt = (
        select(func.count(func.distinct(doc_series.c.doc)).label("doc_cnt"))
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .join(doc_series, true())
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.mode == "project",
            Session.deleted_at.is_(None),
            Message.role == "student",
            func.date(Message.created_at) >= since,
        )
    )
    class_doc_count = int((await session.execute(class_stmt)).scalar_one())

    return {
        "project_students": project_students,
        "student_doc_counts": student_doc_counts,
        "class_doc_count": class_doc_count,
    }


async def list_key_students(
    session: AsyncSession,
    class_ids: list[UUID],
    since: date,
    inactive_threshold_days: int = 7,
) -> list[dict]:
    """重点学生：高风险 / 高优先级。

    规则：
    - high_risk（高风险）：窗口内（Message.created_at >= since）有会话但 AI 从未回复（assistant 消息数=0）
    - high_priority（高优先级）：处于待关注列表（长时间未活跃，inactive_days >= 阈值）
    - 同时命中时优先记 high_risk

    冷启动保护：若整个班级范围内窗口内没有任何 assistant 消息（total_ai == 0），
    说明 message 表刚启用尚无消息数据，跳过所有高风险判定，避免把仅有历史会话的
    学生误标成"AI 未回复"；此时命中待关注的学生仍按高优先级输出。
    """
    # 1. 冷启动保护判定：窗口内班级范围内 AI 回复总数
    total_ai_stmt = (
        select(func.count())
        .select_from(Message)
        .join(Session, Session.id == Message.session_id)
        .join(ClassStudent, ClassStudent.user_id == Session.user_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            Session.deleted_at.is_(None),
            Message.role == "assistant",
            func.date(Message.created_at) >= since,
        )
    )
    total_ai = int((await session.execute(total_ai_stmt)).scalar_one())

    # 2. 班级学生列表（排除已软删学生）
    students_stmt = (
        select(ClassStudent, User, Class)
        .join(User, User.id == ClassStudent.user_id)
        .join(Class, Class.id == ClassStudent.class_id)
        .where(
            ClassStudent.class_id.in_(class_ids),
            User.deleted_at.is_(None),
        )
    )
    rows = (await session.execute(students_stmt)).all()

    results: list[dict] = []
    # 按 user_id 去重，多班学生只出现一次（level/计数均按学生整体计算，与班级无关）
    seen: set[UUID] = set()
    for cs, user, cls in rows:
        if user.id in seen:
            continue
        # 窗口内会话数（该学生整体，未删除）
        session_stmt = (
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id == user.id,
                Session.deleted_at.is_(None),
                func.date(Session.last_active_at) >= since,
            )
        )
        session_count = int((await session.execute(session_stmt)).scalar_one())

        # 窗口内 AI 回复数（该学生）
        ai_stmt = (
            select(func.count())
            .select_from(Message)
            .join(Session, Session.id == Message.session_id)
            .where(
                Session.user_id == user.id,
                Session.deleted_at.is_(None),
                Message.role == "assistant",
                func.date(Message.created_at) >= since,
            )
        )
        ai_count = int((await session.execute(ai_stmt)).scalar_one())

        # 未活跃天数（最后活跃时间距今；无会话 = 999）
        last_active_stmt = (
            select(func.max(Session.last_active_at))
            .select_from(Session)
            .where(Session.user_id == user.id, Session.deleted_at.is_(None))
        )
        last_active = (await session.execute(last_active_stmt)).scalar_one_or_none()
        if last_active is None:
            inactive_days = 999
        else:
            inactive_days = (datetime.now(UTC) - last_active).days

        level: str | None = None
        reason = ""
        if total_ai > 0 and session_count > 0 and ai_count == 0:
            level = "high_risk"
            reason = "窗口内有会话但 AI 从未回复"
        elif inactive_days >= inactive_threshold_days:
            level = "high_priority"
            reason = "长时间未活跃，需跟进"
        if level is None:
            continue
        seen.add(user.id)

        results.append({
            "user_id": user.id,
            "name": user.name,
            "username": user.username,
            "class_id": cls.id,
            "class_name": f"{cls.grade} {cls.classname}",
            "level": level,
            "reason": reason,
            "session_count": session_count,
            "assistant_messages": ai_count,
        })

    # 高风险优先在前，同级别按名称稳定排序
    order = {"high_risk": 0, "high_priority": 1}
    results.sort(key=lambda x: (order[x["level"]], x["name"]))
    return results

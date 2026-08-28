# 班级路由
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.classes import service as class_service
from tutoring.classes.schemas import (
    AddStudentsRequest,
    ClassCreate,
    ClassOut,
    ClassSessionOut,
    ClassStats,
    ClassStudentOut,
    ClassUpdate,
    RemoveStudentsRequest,
)
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.core.schemas import Page
from tutoring.db import repos
from tutoring.db.models import ClassStudent

router = APIRouter(prefix="/classes", tags=["classes"])

# 确保用户是教师
def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可执行此操作")


# ============ 班级 CRUD ============

# 创建班级
@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
async def create_class_endpoint(
    body: ClassCreate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ClassOut:
    _require_teacher(user)
    obj = await class_service.create_class(
        db_session,
        grade=body.grade,
        classname=body.classname,
        teacher_id=user.id,
    )
    return ClassOut(
        id=obj.id,
        grade=obj.grade,
        classname=obj.classname,
        teacher_id=obj.teacher_id,
        status=obj.status,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        student_count=0,
    )

# 获取班级列表
@router.get("", response_model=Page[ClassOut])
async def list_classes(
    teacher_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[ClassOut]:
    _require_teacher(user)
    offset = (page - 1) * page_size

    # 教师默认只看自己的班级
    tid = teacher_id or (user.id if user.role == "teacher" else None)

    classes = await repos.list_classes(
        db_session,
        teacher_id=tid,
        status=status_filter,
        keyword=keyword,
        limit=page_size,
        offset=offset,
    )
    total = await repos.count_classes(
        db_session,
        teacher_id=tid,
        status=status_filter,
        keyword=keyword,
    )

    items = []
    for c in classes:
        items.append(
            ClassOut(
                id=c.id,
                grade=c.grade,
                classname=c.classname,
                teacher_id=c.teacher_id,
                status=c.status,
                created_at=c.created_at,
                updated_at=c.updated_at,
                student_count=len(c.students) if c.students else 0,
                teacher_name=c.teacher.name if c.teacher else None,
            )
        )
    return Page(items=items, total=total, page=page, page_size=page_size)

# 获取班级详情
@router.get("/{class_id}", response_model=ClassOut)
async def get_class(
    class_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ClassOut:
    _require_teacher(user)
    
    obj = await class_service.ensure_class_teacher(db_session, class_id, user.id)
    return ClassOut(
        id=obj.id,
        grade=obj.grade,
        classname=obj.classname,
        teacher_id=obj.teacher_id,
        status=obj.status,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        student_count=len(obj.students) if obj.students else 0,
        teacher_name=obj.teacher.name if obj.teacher else None,
    )

# 更新班级
@router.patch("/{class_id}", response_model=ClassOut)
async def update_class(
    class_id: UUID,
    body: ClassUpdate,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ClassOut:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise AppError(422, "VALIDATION_ERROR", "No fields to update")
    obj = await repos.update_class(db_session, class_id, **fields)
    if not obj:
        raise AppError(404, "CLASS_NOT_FOUND", f"Class {class_id} not found")
    return ClassOut(
        id=obj.id,
        grade=obj.grade,
        classname=obj.classname,
        teacher_id=obj.teacher_id,
        status=obj.status,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        student_count=len(obj.students) if obj.students else 0,
        teacher_name=obj.teacher.name if obj.teacher else None,
    )

# 删除班级
@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    await repos.delete_class(db_session, class_id)


# ============ 班级学生管理 ============

# 批量添加班级学生
@router.post("/{class_id}/students", status_code=status.HTTP_201_CREATED)
async def add_students_to_class(
    class_id: UUID,
    body: AddStudentsRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    count = await class_service.add_students(db_session, class_id, body.user_ids)
    return {"added": count}

# 移除班级学生
@router.delete("/{class_id}/students/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student_from_class(
    class_id: UUID,
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    await class_service.remove_student(db_session, class_id, user_id)

# 批量移除班级学生
@router.post("/{class_id}/students/bulk-remove")
async def bulk_remove_students_from_class(
    class_id: UUID,
    body: RemoveStudentsRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    count = await class_service.bulk_remove_students(db_session, class_id, body.user_ids)
    return {"removed": count}

# 获取班级学生列表
@router.get("/{class_id}/students", response_model=Page[ClassStudentOut])
async def list_class_students(
    class_id: UUID,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[ClassStudentOut]:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    offset = (page - 1) * page_size
    items = await repos.list_class_students(
        db_session, class_id, keyword=keyword, limit=page_size, offset=offset
    )
    total = await repos.count_class_students(db_session, class_id, keyword=keyword)
    return Page(
        items=[
            ClassStudentOut(
                user_id=cs.user.id,
                username=cs.user.username,
                name=cs.user.name,
                joined_at=cs.joined_at,
            )
            for cs in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============ 班级对话查看 ============

@router.get("/{class_id}/sessions", response_model=Page[ClassSessionOut])
async def list_class_sessions(
    class_id: UUID,
    mode: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[ClassSessionOut]:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    offset = (page - 1) * page_size
    sessions = await repos.count_class_sessions(
        db_session, class_id, mode=mode, limit=page_size, offset=offset
    )
    total = await repos.count_class_sessions(db_session, class_id, mode=mode)
    return Page(
        items=[
            ClassSessionOut(
                id=s.id,
                user_id=s.user_id,
                user_name=s.user.name if s.user else None,
                title=s.title,
                mode=s.mode,
                project_id=s.project_id,
                project_name=s.project.name if s.project else None,
                last_active_at=s.last_active_at,
                created_at=s.created_at,
            )
            for s in sessions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============ 班级统计 ============

@router.get("/{class_id}/stats", response_model=ClassStats)
async def get_class_stats(
    class_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ClassStats:
    _require_teacher(user)
    await class_service.ensure_class_teacher(db_session, class_id, user.id)
    stats = await repos.get_class_stats(db_session, class_id)
    return ClassStats(**stats)
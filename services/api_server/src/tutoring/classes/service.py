from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Class, User

# 创建班级
async def create_class(
    db: AsyncSession, *, grade: str, classname: str, teacher_id: UUID
) -> Class:
    obj = await repos.create_class(
        db, grade=grade, classname=classname, teacher_id=teacher_id
    )
    return obj

# 获取班级
async def get_class_or_404(db: AsyncSession, class_id: UUID) -> Class:
    obj = await repos.get_class(db, class_id)
    if not obj:
        raise AppError(404, "CLASS_NOT_FOUND", f"Class {class_id} not found")
    return obj

# 确保班级授课教师
async def ensure_class_teacher(db: AsyncSession, class_id: UUID, user_id: UUID) -> Class:
    """确保当前用户是该班级的授课教师，否则抛 403。"""
    obj = await get_class_or_404(db, class_id)
    if obj.teacher_id != user_id:
        raise AppError(403, "NOT_CLASS_TEACHER", "仅授课教师可操作此班级")
    return obj

# 批量添加班级学生
async def add_students(
    db: AsyncSession, class_id: UUID, user_ids: list[UUID]
) -> int:
    count = await repos.add_students_to_class(db, class_id, user_ids)
    return count

# 移除班级学生
async def remove_student(
    db: AsyncSession, class_id: UUID, user_id: UUID
) -> None:
    await repos.remove_student_from_class(db, class_id, user_id)

# 批量移除班级学生
async def bulk_remove_students(
    db: AsyncSession, class_id: UUID, user_ids: list[UUID]
) -> int:
    return await repos.bulk_remove_students_from_class(db, class_id, user_ids)
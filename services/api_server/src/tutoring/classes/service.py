import io
from openpyxl import load_workbook
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Class
from tutoring.classes.schemas import ImportResult
from tutoring.auth.service import hash_password

DEFAULT_PASSWORD = "123456"
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

# 导入班级学生
async def import_students(db: AsyncSession, file_bytes: bytes) -> ImportResult:
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    total = len(rows)
    created = 0
    skipped = 0
    errors: list[str] = []
    seen: set[str] = set()

    for i, row in enumerate(rows, start=2):
        if not row or len(row) < 3:
            errors.append(f"第{i}行: 数据不完整")
            continue
        username, name, password = str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip()
        if not username or not name or not password:
            errors.append(f"第{i}行: 学号/姓名/密码不能为空")
            continue
        if username in seen:
            skipped += 1
            continue
        seen.add(username)

        existing = await repos.get_user_by_username(db, username)
        if existing:
            skipped += 1
            continue

        await repos.create_user(
            db,
            username=username,
            password_hash=hash_password(password),
            role="student",
            name=name,
        )
        created += 1

    return ImportResult(total=total, created=created, skipped=skipped, errors=errors)

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

# 重置班级学生密码
async def reset_password(db: AsyncSession, user_id) -> None:
    user = await repos.get_user_by_id(db, user_id)
    if not user:
        raise AppError(404, "USER_NOT_FOUND", f"User {user_id} not found")
    await repos.update_password(db, user_id, hash_password(DEFAULT_PASSWORD))
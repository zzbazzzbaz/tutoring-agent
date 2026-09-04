import io
from openpyxl import load_workbook
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Class
from tutoring.classes.schemas import ImportResult
from tutoring.auth.service import hash_password

# 创建班级
async def create_class(
    db: AsyncSession, *, grade: str, classname: str, teacher_id: UUID
) -> Class:
    # 同教师 + 同年级 + 同班级名 不得重复（排除已软删班级）
    await ensure_class_name_unique(
        db, teacher_id=teacher_id, grade=grade, classname=classname
    )
    obj = await repos.create_class(
        db, grade=grade, classname=classname, teacher_id=teacher_id
    )
    return obj

# 校验班级名唯一
async def ensure_class_name_unique(
    db: AsyncSession,
    *,
    teacher_id: UUID,
    grade: str,
    classname: str,
    exclude_id: UUID | None = None,
) -> None:
    """校验「同教师+同年级+同班级名」唯一（排除已软删班级），冲突抛 409。
    exclude_id 用于编辑场景：排除当前班级自身。"""
    existing = await repos.get_class_by_teacher_grade_name(
        db, teacher_id=teacher_id, grade=grade, classname=classname
    )
    if existing and (exclude_id is None or existing.id != exclude_id):
        raise AppError(
            409,
            "CLASS_NAME_EXISTS",
            f"同年级已存在班级「{classname}」，请勿重复创建",
        )

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
async def import_students(db: AsyncSession, class_id: UUID, file_bytes: bytes) -> ImportResult:
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    total = len(rows)
    created = 0
    # 已存在且未删除的学生账号，并入当前班级的数量
    joined_existing = 0
    skipped = 0
    errors: list[str] = []
    seen: set[str] = set()

    for i, row in enumerate(rows, start=2):
        if not row or len(row) < 2:
            errors.append(f"第{i}行: 数据不完整")
            continue
        username = str(row[0]).strip() if row[0] is not None else ""
        name = str(row[1]).strip() if row[1] is not None else ""

        if not username:
            errors.append(f"第{i}行: 学号不能为空")
            continue
        if not username.isdigit():
            errors.append(f"第{i}行: 学号必须为纯数字")
            continue
        if len(username) < 9:
            errors.append(f"第{i}行: 学号长度不足9位")
            continue
        if not name:
            errors.append(f"第{i}行: 姓名不能为空")
            continue

        if username in seen:
            skipped += 1
            continue
        seen.add(username)

        existing = await repos.get_user_by_username(db, username)
        if existing:
            # 已存在账号若是【未删除学生】→ 幂等并入当前班级
            # （add_students_to_class 忽略已在班成员），不再静默跳过；
            # 教师账号 / 已软删账号仍按跳过处理，不复活、不入班。
            if existing.role == "student" and existing.deleted_at is None:
                await repos.add_students_to_class(db, class_id, [existing.id])
                joined_existing += 1
            else:
                skipped += 1
            continue

        password = username[-6:]
        user = await repos.create_user(
            db,
            username=username,
            password_hash=hash_password(password),
            role="student",
            name=name,
        )
        await repos.add_students_to_class(db, class_id, [user.id])
        created += 1

    return ImportResult(
        total=total,
        created=created,
        joined_existing=joined_existing,
        skipped=skipped,
        errors=errors,
    )

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

# 批量软删除学生账号
async def bulk_delete_students(
    db: AsyncSession,
    class_id: UUID,
    user_ids: list[UUID],
    *,
    reason: str,
    deleted_by: UUID,
) -> int:
    """批量软删学生账号：仅删除【本班级】的【未删除学生】账号，
    教师/其他班学生/已删除账号一律跳过，防止任一教师封禁任意账号。"""
    allowed: list[UUID] = []
    for uid in user_ids:
        user = await repos.get_user_by_id(db, uid)
        if not user or user.deleted_at is not None:
            continue  # 不存在或已删除
        if user.role != "student":
            continue  # 非学生账号（如教师）不得删除
        if not await repos.check_class_member(db, class_id, uid):
            continue  # 不属于当前班级
        allowed.append(uid)
    if not allowed:
        return 0
    return await repos.soft_delete_users(
        db, allowed, reason=reason, deleted_by=deleted_by
    )

# 重置班级学生密码
async def reset_password(db: AsyncSession, class_id: UUID, user_id: UUID) -> None:
    """重置密码：仅允许授课教师重置【本班级】的【未删除学生】账号。"""
    user = await repos.get_user_by_id(db, user_id)
    if not user or user.deleted_at is not None:
        raise AppError(404, "USER_NOT_FOUND", f"User {user_id} not found")
    if user.role != "student":
        raise AppError(403, "NOT_STUDENT", "只能重置学生账号的密码")
    if not await repos.check_class_member(db, class_id, user_id):
        raise AppError(403, "NOT_CLASS_MEMBER", "该学生不属于此班级")
    new_password = user.username[-6:]
    await repos.update_password(db, user_id, hash_password(new_password))
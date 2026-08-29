import io
import os

from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth.service import hash_password
from tutoring.core.config import settings
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import User
# from tutoring.users.schemas import ImportResult  # 已注释：ImportResult schema 被注释掉，对应的 import_students 也废弃

DEFAULT_PASSWORD = "123456"

ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB
AVATAR_EXT_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


""" async def list_students(
    db: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[User]:
    if limit is None:
        return await repos.list_users_by_role(db, "student")
    return await repos.list_users_by_role_paginated(db, "student", limit=limit, offset=offset) """


async def list_teachers(db: AsyncSession) -> list[User]:
    return await repos.list_users_by_role(db, "teacher")


""" async def delete_student(db: AsyncSession, user_id) -> None:
    user = await repos.get_user_by_id(db, user_id)
    if not user:
        raise AppError(404, "USER_NOT_FOUND", f"User {user_id} not found")
    if user.role != "student":
        raise AppError(403, "CAN_ONLY_DELETE_STUDENT", "只能删除学生账号")
    await repos.delete_user(db, user_id) """


""" async def reset_password(db: AsyncSession, user_id) -> None:
    user = await repos.get_user_by_id(db, user_id)
    if not user:
        raise AppError(404, "USER_NOT_FOUND", f"User {user_id} not found")
    await repos.update_password(db, user_id, hash_password(DEFAULT_PASSWORD)) """


""" async def import_students(db: AsyncSession, file_bytes: bytes) -> ImportResult:
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

    return ImportResult(total=total, created=created, skipped=skipped, errors=errors) """


async def upload_avatar(db: AsyncSession, user_id, file_content: bytes, content_type: str) -> str:
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise AppError(422, "INVALID_FILE_TYPE", "仅支持 PNG/JPEG/WebP/GIF 格式")
    if len(file_content) > MAX_AVATAR_SIZE:
        raise AppError(422, "FILE_TOO_LARGE", "头像文件不能超过 5MB")

    ext = AVATAR_EXT_MAP[content_type]
    filename = f"{user_id}{ext}"
    avatars_dir = os.path.join(settings.upload_dir, "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    file_path = os.path.join(avatars_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_content)

    avatar_url = f"/media/avatars/{filename}"
    await repos.update_avatar_url(db, user_id, avatar_url)
    return avatar_url

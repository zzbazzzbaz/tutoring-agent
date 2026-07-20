"""种子脚本：重建表 + 插入测试账号。

用法：uv run python scripts/seed_users.py

会 DROP session/message/question/auth_token/user 表后重建（projects 保留）。
插入：1 教师 + 2 学生。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncEngine

from tutoring.auth.service import hash_password
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory
from tutoring.db import repos
from tutoring.db import models  # noqa: F401 - register tables on metadata


TABLES_TO_DROP = ["session", "message", "question", "auth_token", "user"]


async def main() -> None:
    engine: AsyncEngine = create_engine(settings.database_url)

    # 1. Drop old tables (projects 保留)
    print("Dropping old tables...")
    async with engine.begin() as conn:
        for table in TABLES_TO_DROP:
            await conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        print("  done")

    # 2. Create all tables
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("  done")

    # 3. Insert seed users
    session_factory = create_session_factory(engine)
    async with session_factory() as db:
        teacher = await repos.create_user(
            db,
            username="teacher1",
            password_hash=hash_password("teacher123"),
            role="teacher",
            name="测试教师",
        )
        print(f"  teacher: {teacher.username} / {teacher.id}")

        for i in range(1, 3):
            student = await repos.create_user(
                db,
                username=f"student{i}",
                password_hash=hash_password("student123"),
                role="student",
                name=f"测试学生{i}",
            )
            print(f"  student: {student.username} / {student.id}")

    await engine.dispose()
    print("\nSeed complete. Login:")
    print("  teacher: teacher1 / teacher123")
    print("  student: student1 / student123")


if __name__ == "__main__":
    asyncio.run(main())

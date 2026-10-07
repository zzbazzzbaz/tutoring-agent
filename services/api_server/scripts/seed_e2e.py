"""E2E 种子脚本：重建表 + 插入平时分 E2E 确定性数据。

用法：uv run python scripts/seed_e2e.py（仅本地/测试环境，会清空业务数据）

数据：1 教师 teacher1/teacher123；1 班级（2025级 1班）含 3 名学生；
student1 两个会话完整对话（含知识命中）、student2 一个会话少量消息、student3 无数据。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

from tutoring.auth.service import hash_password
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory
from tutoring.db import (
    models,  # noqa: F401 - register tables on metadata
    repos,
)

TABLES_TO_DROP = [
    "session",
    "message",
    "question",
    "auth_token",
    "user",
    "project",
    "class",
    "class_student",
    "session_progress",
    "scoring_prompt",
    "student_score",
]

_STUDENT_TURNS = [
    ("什么是注意的稳定性？", True, ["普通心理学/注意.md"]),
    ("那注意的分配和转移有什么区别？", True, ["普通心理学/注意.md"]),
    ("幼儿的注意一般能维持多久？", False, []),
]


async def main() -> None:
    engine: AsyncEngine = create_engine(settings.database_url)

    async with engine.begin() as conn:
        for table in TABLES_TO_DROP:
            await conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory() as db:
        teacher = await repos.create_user(
            db,
            username="teacher1",
            password_hash=hash_password("teacher123"),
            role="teacher",
            name="测试教师",
        )
        cls = await repos.create_class(
            db, grade="2025级", classname="1班", teacher_id=teacher.id
        )

        students = []
        for i in range(1, 4):
            stu = await repos.create_user(
                db,
                username=f"student{i}",
                password_hash=hash_password("student123"),
                role="student",
                name=f"测试学生{i}",
            )
            students.append(stu)
        await repos.add_students_to_class(db, cls.id, [s.id for s in students])

        for _ in range(2):
            sess = await repos.create_session(db, mode="free", user_id=students[0].id)
            for question, hit, doc_ids in _STUDENT_TURNS:
                await repos.create_messages(
                    db,
                    session_id=sess.id,
                    items=[
                        {
                            "role": "student",
                            "content": question,
                            "knowledge_hit": hit,
                            "knowledge_doc_ids": doc_ids,
                        },
                        {"role": "assistant", "content": "先说说你自己的理解？"},
                    ],
                )

        sess2 = await repos.create_session(db, mode="free", user_id=students[1].id)
        await repos.create_messages(
            db,
            session_id=sess2.id,
            items=[
                {
                    "role": "student",
                    "content": "我想了解记忆的分类",
                    "knowledge_hit": True,
                    "knowledge_doc_ids": ["普通心理学/记忆.md"],
                },
                {"role": "assistant", "content": "你觉得记忆可以怎么分类？"},
            ],
        )

        print("E2E seed complete:")
        print("  teacher : teacher1 / teacher123")
        print("  students: student1 / student2 / student3（密码均 student123，student3 无使用数据）")
        print(f"  class   : {cls.grade} {cls.classname} id={cls.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

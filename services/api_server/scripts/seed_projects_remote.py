"""将 SEED_PROJECTS 中的 3 个项目插入远程数据库（已存在则更新）。

用法：uv run python scripts/seed_projects_remote.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select

from tutoring.core.database import create_engine, create_session_factory
from tutoring.db import models  # noqa: F401
from tutoring.db.models import Project
from tutoring.db.repos import create_project, update_project

from seed_users2 import SEED_PROJECTS

REMOTE_DB_URL = (
    "postgresql+asyncpg://tutoring:"
    "de062c5fcc52c79878f741599f202f6e86b35148b97df756d54d3df27cbb11bd"
    "@82.157.111.219:10000/tutoring_db"
)


async def main() -> None:
    engine: AsyncEngine = create_engine(REMOTE_DB_URL)
    session_factory = create_session_factory(engine)

    async with session_factory() as db:
        for project_data in SEED_PROJECTS:
            name = project_data["name"]
            result = await db.execute(select(Project).where(Project.name == name))
            existing = result.scalars().first()

            if existing:
                await update_project(
                    db,
                    existing.id,
                    background_md=project_data["background_md"],
                    status=project_data["status"],
                )
                print(f"  updated: {name} / {existing.id}")
            else:
                project = await create_project(db, **project_data)
                print(f"  created: {name} / {project.id}")

    await engine.dispose()
    print("\nDone. 3 projects synced to remote database.")


if __name__ == "__main__":
    asyncio.run(main())

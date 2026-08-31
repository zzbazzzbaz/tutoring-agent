from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.core.errors import AppError
from tutoring.progress import service as progress_service


class _ExistingProjectDB:
    def __init__(self):
        self.project = SimpleNamespace(id=uuid4(), deleted_at=None)
        self.stored = {}

    async def get(self, model, project_id):
        if model.__name__ == "Project":
            return self.project if self.project.id == project_id else None
        return self.stored.get(project_id)


class _MissingProjectDB:
    async def get(self, _model, _project_id):
        return None


@pytest.mark.asyncio
async def test_update_progress_merges_into_existing(monkeypatch):
    merged = {}

    async def fake_upsert(_db, *, user_id, project_id, progress):
        merged.update(progress)

    async def fake_get(_db, *, user_id, project_id):
        return SimpleNamespace(progress=merged)

    monkeypatch.setattr("tutoring.db.repos.upsert_project_progress", fake_upsert)
    monkeypatch.setattr("tutoring.db.repos.get_project_progress", fake_get)

    db = _ExistingProjectDB()
    await progress_service.update_progress(
        db, user_id=uuid4(), project_id=db.project.id, progress={"stg_01": {"status": "in_progress"}}
    )
    await progress_service.update_progress(
        db,
        user_id=uuid4(),
        project_id=db.project.id,
        progress={"stg_01": {"status": "completed", "deliverable_done": True}},
    )

    assert merged["stg_01"]["status"] == "completed"
    assert merged["stg_01"]["deliverable_done"] is True


@pytest.mark.asyncio
async def test_update_progress_rejects_missing_project():
    with pytest.raises(AppError) as exc_info:
        await progress_service.update_progress(
            _MissingProjectDB(),
            user_id=uuid4(),
            project_id=uuid4(),
            progress={"stg_01": {"status": "in_progress"}},
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_progress_returns_empty_for_new_user():
    class _NoProgressDB(_ExistingProjectDB):
        async def get(self, model, project_id):
            if model.__name__ == "Project":
                return self.project
            return None

    db = _NoProgressDB()
    result = await progress_service.get_progress(
        db, user_id=uuid4(), project_id=db.project.id
    )
    assert result.progress == {}

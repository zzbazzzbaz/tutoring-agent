from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.core.errors import AppError
from tutoring.progress import service as progress_service


class _ExistingSessionDB:
    def __init__(self):
        self.session = SimpleNamespace(id=uuid4(), deleted_at=None)
        self.stored = {}

    async def get(self, model, session_id):
        if model.__name__ == "Session":
            return self.session if self.session.id == session_id else None
        return self.stored.get(session_id)


class _MissingSessionDB:
    async def get(self, _model, _session_id):
        return None


@pytest.mark.asyncio
async def test_update_progress_merges_into_existing(monkeypatch):
    merged = {}

    async def fake_upsert(_db, *, session_id, progress):
        merged.update(progress)

    async def fake_get(_db, *, session_id):
        return SimpleNamespace(progress=merged)

    monkeypatch.setattr("tutoring.db.repos.upsert_session_progress", fake_upsert)
    monkeypatch.setattr("tutoring.db.repos.get_session_progress", fake_get)

    db = _ExistingSessionDB()
    await progress_service.update_progress(
        db, session_id=db.session.id, progress={"stg_01": {"status": "in_progress"}}
    )
    await progress_service.update_progress(
        db,
        session_id=db.session.id,
        progress={"stg_01": {"status": "completed", "deliverable_done": True}},
    )

    assert merged["stg_01"]["status"] == "completed"
    assert merged["stg_01"]["deliverable_done"] is True


@pytest.mark.asyncio
async def test_update_progress_rejects_missing_session():
    with pytest.raises(AppError) as exc_info:
        await progress_service.update_progress(
            _MissingSessionDB(),
            session_id=uuid4(),
            progress={"stg_01": {"status": "in_progress"}},
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_progress_returns_empty_for_new_session():
    class _NoProgressDB(_ExistingSessionDB):
        async def get(self, model, session_id):
            if model.__name__ == "Session":
                return self.session
            return None

    db = _NoProgressDB()
    result = await progress_service.get_progress(db, session_id=db.session.id)
    assert result.progress == {}

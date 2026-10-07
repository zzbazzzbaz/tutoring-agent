from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from tutoring.core.errors import AppError
from tutoring.projects import service as project_service
from tutoring.projects.schemas import AgentCaseDraftIn, AgentCaseDraftStage


def _stage(**overrides) -> AgentCaseDraftStage:
    base = {"title": "情绪与分离焦虑"}
    base.update(overrides)
    return AgentCaseDraftStage(**base)


def test_agent_case_draft_requires_deliverable_instructions():
    with pytest.raises(ValidationError):
        AgentCaseDraftIn(
            name="案例A",
            background_md="背景",
            objective="目标",
            stages=[{"title": "阶段一", "deliverable_title": "观察记录"}],
        )


@pytest.mark.asyncio
async def test_save_agent_draft_builds_normalized_mainline(monkeypatch):
    captured: dict = {}
    proj = SimpleNamespace(id=uuid4(), name="案例A")

    async def fake_create(_db, *, name, background_md, status, mainline):
        captured.update(name=name, status=status, mainline=mainline)
        return proj

    monkeypatch.setattr("tutoring.db.repos.create_project", fake_create)

    result, created = await project_service.save_agent_draft(
        None,
        project_id=None,
        name="案例A",
        background_md="背景",
        objective="目标",
        stages=[
            _stage(deliverable_title="观察记录", deliverable_instructions="记录 3 个案例"),
            _stage(title="注意与活动设计"),
        ],
    )

    assert created is True and result is proj
    assert captured["status"] == "draft"
    stages = captured["mainline"]["stages"]
    assert stages[0]["id"] == "stg_01" and stages[0]["order"] == 1
    assert stages[0]["deliverable"] == {"title": "观察记录", "instructions": "记录 3 个案例"}
    assert stages[1]["id"] == "stg_02" and stages[1]["deliverable"] is None


@pytest.mark.asyncio
async def test_save_agent_draft_name_conflict(monkeypatch):
    class _DB:
        async def rollback(self):
            pass

    async def fake_create(_db, **_kwargs):
        raise IntegrityError("stmt", {}, Exception("duplicate"))

    monkeypatch.setattr("tutoring.db.repos.create_project", fake_create)

    with pytest.raises(AppError) as exc_info:
        await project_service.save_agent_draft(
            _DB(),
            project_id=None,
            name="案例A",
            background_md="背景",
            objective="目标",
            stages=[_stage()],
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_save_agent_draft_updates_existing(monkeypatch):
    project_id = uuid4()
    existing = SimpleNamespace(id=project_id, deleted_at=None)
    updated = SimpleNamespace(id=project_id, name="案例A")

    async def fake_get(_db, _pid):
        return existing

    async def fake_update(_db, _pid, **fields):
        return updated

    monkeypatch.setattr("tutoring.db.repos.get_project", fake_get)
    monkeypatch.setattr("tutoring.db.repos.update_project", fake_update)

    result, created = await project_service.save_agent_draft(
        None,
        project_id=project_id,
        name="案例A",
        background_md="背景",
        objective="目标",
        stages=[_stage()],
    )
    assert created is False and result is updated

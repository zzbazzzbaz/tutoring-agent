from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.core.deps import CurrentUser
from tutoring.projects import router as projects_router
from tutoring.sessions import router as sessions_router
from tutoring.sessions.schemas import SessionUpdate
from tutoring.users import router as users_router


def _teacher() -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        username="teacher",
        role="teacher",
        name="Teacher",
    )


def _session(**overrides):
    data = {
        "id": uuid4(),
        "user_id": uuid4(),
        "mode": "free",
        "project_id": None,
        "project": None,
        "title": "自由学习",
        "last_active_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_list_students_returns_paginated_response(monkeypatch):
    async def fake_list_students(_db, *, limit: int, offset: int):
        assert limit == 10
        assert offset == 10
        return [
            SimpleNamespace(
                id=uuid4(),
                username="2023001",
                role="student",
                name="张三",
                avatar_url=None,
                created_at=datetime.now(UTC),
            )
        ]

    async def fake_count_users_by_role(_db, role: str):
        assert role == "student"
        return 21

    monkeypatch.setattr(users_router.user_service, "list_students", fake_list_students)
    monkeypatch.setattr(users_router.repos, "count_users_by_role", fake_count_users_by_role)

    result = await users_router.list_students(
        page=2,
        page_size=10,
        user=_teacher(),
        db_session=object(),
    )

    assert result.page == 2
    assert result.page_size == 10
    assert result.total == 21
    assert result.items[0].username == "2023001"


@pytest.mark.asyncio
async def test_list_user_sessions_returns_paginated_response(monkeypatch):
    student_id = uuid4()

    async def fake_list_sessions(_db, *, user_id, mode, limit: int, offset: int):
        assert user_id == student_id
        assert mode is None
        assert limit == 5
        assert offset == 10
        return [_session(user_id=student_id, title="阶段复盘")]

    async def fake_count_sessions(_db, *, user_id, mode):
        assert user_id == student_id
        assert mode is None
        return 13

    monkeypatch.setattr(users_router.repos, "list_sessions", fake_list_sessions)
    monkeypatch.setattr(users_router.repos, "count_sessions", fake_count_sessions)

    result = await users_router.list_user_sessions(
        user_id=student_id,
        mode=None,
        page=3,
        page_size=5,
        user=_teacher(),
        db_session=object(),
    )

    assert result.page == 3
    assert result.page_size == 5
    assert result.total == 13
    assert result.items[0].title == "阶段复盘"


@pytest.mark.asyncio
async def test_list_projects_returns_paginated_response(monkeypatch):
    async def fake_list_projects(_db, *, status, limit: int, offset: int):
        assert status == "published"
        assert limit == 20
        assert offset == 20
        return [
            SimpleNamespace(
                id=uuid4(),
                name="项目 A",
                background_md="# 背景",
                status="published",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ]

    async def fake_count_projects(_db, *, status):
        assert status == "published"
        return 41

    monkeypatch.setattr(projects_router.repos, "list_projects", fake_list_projects)
    monkeypatch.setattr(projects_router.repos, "count_projects", fake_count_projects)

    result = await projects_router.list_projects(
        status="published",
        page=2,
        page_size=20,
        user=_teacher(),
        db_session=object(),
    )

    assert result.page == 2
    assert result.page_size == 20
    assert result.total == 41
    assert result.items[0].name == "项目 A"


@pytest.mark.asyncio
async def test_update_session_title_trims_title(monkeypatch):
    session_id = uuid4()
    sess = _session(id=session_id, title="旧标题")

    async def fake_get_writable_session(_db, requested_id, _user):
        assert requested_id == session_id
        return sess

    async def fake_update_session_title(_db, requested_id, title: str):
        assert requested_id == session_id
        assert title == "新标题"
        sess.title = title
        return sess

    monkeypatch.setattr(
        sessions_router.session_service,
        "get_writable_session",
        fake_get_writable_session,
    )
    monkeypatch.setattr(
        sessions_router.repos,
        "update_session_title",
        fake_update_session_title,
    )

    result = await sessions_router.update_session(
        session_id=session_id,
        body=SessionUpdate(title="  新标题  "),
        user=_teacher(),
        db_session=object(),
    )

    assert result.title == "新标题"

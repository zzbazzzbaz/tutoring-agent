from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.auth import router
from tutoring.auth.schemas import AgentAuthorizeRequest
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError


def _user(role: str = "student") -> CurrentUser:
    return CurrentUser(id=uuid4(), username="student", role=role, name="Student")


def test_agent_server_secret_is_required():
    router.require_agent_server(settings.agent_server_secret)

    with pytest.raises(AppError) as exc_info:
        router.require_agent_server("wrong-secret")

    assert exc_info.value.status == 403
    assert exc_info.value.code == "INVALID_AGENT_SERVER"


@pytest.mark.asyncio
async def test_identity_authorization_returns_safe_claims():
    user = _user()

    result = await router.authorize_agent_request(
        AgentAuthorizeRequest(access="identity"), user, SimpleNamespace()
    )

    assert result.identity == str(user.id)
    assert result.session_access == "identity"
    assert result.session_id is None
    assert result.agent_context is None


@pytest.mark.asyncio
async def test_run_authorization_uses_writable_session_and_touches_it(monkeypatch):
    session_id = uuid4()
    session = SimpleNamespace(id=session_id)
    calls = []

    async def get_writable(db, requested_id, user):
        calls.append(("write", requested_id, user.id))
        return session

    async def touch(db, requested_id):
        calls.append(("touch", requested_id))

    async def build_context(db, authorized_session):
        assert authorized_session is session
        return {"mode": "free"}

    monkeypatch.setattr(router.session_service, "get_writable_session", get_writable)
    monkeypatch.setattr(router.session_service, "touch_session", touch)
    monkeypatch.setattr(router.session_service, "build_agent_context", build_context)
    user = _user()

    result = await router.authorize_agent_request(
        AgentAuthorizeRequest(session_id=session_id, access="run", touch=True),
        user,
        SimpleNamespace(),
    )

    assert calls == [("write", session_id, user.id), ("touch", session_id)]
    assert result.session_access == "run"
    assert result.agent_context.mode == "free"


@pytest.mark.asyncio
async def test_read_authorization_uses_readable_session_without_touch(monkeypatch):
    session_id = uuid4()
    session = SimpleNamespace(id=session_id)

    async def get_readable(db, requested_id, user):
        assert requested_id == session_id
        return session

    async def build_context(db, authorized_session):
        return {
            "mode": "project",
            "project_name": "网络规划",
            "project_background_md": "项目背景",
        }

    monkeypatch.setattr(router.session_service, "get_readable_session", get_readable)
    monkeypatch.setattr(router.session_service, "build_agent_context", build_context)

    result = await router.authorize_agent_request(
        AgentAuthorizeRequest(session_id=session_id, access="read"),
        _user(role="teacher"),
        SimpleNamespace(),
    )

    assert result.session_access == "read"
    assert result.agent_context.project_name == "网络规划"

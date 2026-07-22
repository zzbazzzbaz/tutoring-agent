from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph_sdk import Auth

from teaching_agent import auth as auth_module
from teaching_agent.backend_client import BackendAuthorizationError
from teaching_agent.schemas import AgentContextV1, AuthorizedPrincipal


@pytest.mark.asyncio
async def test_authenticate_run_uses_backend(monkeypatch):
    session_id = uuid4()
    received = {}

    async def fake_authorize(authorization, **kwargs):
        received.update(authorization=authorization, **kwargs)
        return AuthorizedPrincipal(
            identity=str(uuid4()),
            role="student",
            name="Student",
            session_id=session_id,
            session_access="run",
            agent_context=AgentContextV1(mode="free", course_name="网络"),
        )

    monkeypatch.setattr(auth_module, "authorize_with_backend", fake_authorize)

    result = await auth_module.authenticate(
        path=f"/threads/{session_id}/runs/stream",
        method="POST",
        path_params={"thread_id": str(session_id)},
        authorization="Bearer token",
    )

    assert received == {
        "authorization": "Bearer token",
        "session_id": session_id,
        "access": "run",
        "touch": True,
    }
    assert result["agent_context"]["course_name"] == "网络"
    assert "threads:run" in result["permissions"]


@pytest.mark.asyncio
async def test_authenticate_fails_closed(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise BackendAuthorizationError(503, "unavailable")

    monkeypatch.setattr(auth_module, "authorize_with_backend", unavailable)

    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await auth_module.authenticate(
            path="/info",
            method="GET",
            path_params=None,
            authorization="Bearer token",
        )

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_bearer():
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await auth_module.authenticate(
            path="/info",
            method="GET",
            path_params=None,
            authorization=None,
        )

    assert exc_info.value.status_code == 401


def test_thread_id_falls_back_to_request_path():
    session_id = uuid4()
    assert auth_module._thread_id(f"/threads/{session_id}/state", {}) == session_id


@pytest.mark.parametrize("action", ["count", "prune", "search"])
def test_thread_collection_action_is_not_treated_as_thread_id(action):
    assert auth_module._thread_id(f"/threads/{action}", {}) is None


@pytest.mark.asyncio
async def test_create_thread_stamps_authenticated_owner():
    value = {"metadata": {"graph_id": "tutor"}}

    filters = await auth_module.create_thread(
        SimpleNamespace(user=SimpleNamespace(identity="student-1")), value
    )

    assert filters == {"owner": "student-1"}
    assert value["metadata"] == {"graph_id": "tutor", "owner": "student-1"}


@pytest.mark.asyncio
async def test_create_run_stamps_owner_and_removes_client_context():
    session_id = uuid4()
    user = SimpleNamespace(
        identity="user-1", session_id=str(session_id), session_access="run"
    )
    value = {
        "thread_id": session_id,
        "metadata": {},
        "kwargs": {"context": {"course_name": "伪造课程"}, "input": {}},
    }

    filters = await auth_module.create_run(SimpleNamespace(user=user), value)

    assert filters == {"owner": "user-1"}
    assert value["metadata"] == {"owner": "user-1"}
    assert "context" not in value["kwargs"]


@pytest.mark.asyncio
async def test_student_read_is_owner_filtered_and_teacher_read_is_authorized():
    session_id = uuid4()
    value = {"thread_id": session_id}
    student = SimpleNamespace(identity="student-1", role="student", session_id=session_id)
    teacher = SimpleNamespace(identity="teacher-1", role="teacher", session_id=session_id)

    assert await auth_module.read_thread(SimpleNamespace(user=student), value) == {
        "owner": "student-1"
    }
    assert await auth_module.read_thread(SimpleNamespace(user=teacher), value) is None

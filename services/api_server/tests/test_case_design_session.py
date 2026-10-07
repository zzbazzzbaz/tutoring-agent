from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tutoring.auth import service as auth_service
from tutoring.core.errors import AppError
from tutoring.sessions.router import create_session
from tutoring.sessions.schemas import SessionCreate


@pytest.mark.asyncio
async def test_case_design_session_requires_teacher():
    student = SimpleNamespace(id=uuid4(), role="student")
    with pytest.raises(AppError) as exc_info:
        await create_session(SessionCreate(mode="case_design"), user=student, db_session=None)
    assert exc_info.value.status_code == 403


def test_case_design_session_rejects_project_id():
    with pytest.raises(ValidationError):
        SessionCreate(mode="case_design", project_id=uuid4())


@pytest.mark.asyncio
async def test_build_agent_context_case_design():
    sess = SimpleNamespace(mode="case_design", project_id=None)
    assert await auth_service.build_agent_context(None, sess) == {"mode": "case_design"}

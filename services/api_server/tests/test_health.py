from types import SimpleNamespace

import pytest

from tutoring.core.health import health


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
        return None

    async def execute(self, _query: object) -> None:
        pass


@pytest.mark.asyncio
async def test_health_checks_database_only():
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db_session_factory=_Session))
    )

    result = await health(request)

    assert result["status"] == "healthy"
    assert result["components"] == {"database": "ok"}

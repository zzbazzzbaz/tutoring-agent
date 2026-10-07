import json

import pytest

from teaching_agent.tools.case_design import create_save_case_draft_tool


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    response: _FakeResponse
    calls: list = []

    def __init__(self, timeout: float):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, url, headers=None, json=None):
        _FakeAsyncClient.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeAsyncClient.response


@pytest.fixture
def fake_http(monkeypatch):
    _FakeAsyncClient.calls = []

    def _install(status_code: int, payload: dict):
        _FakeAsyncClient.response = _FakeResponse(status_code, payload)
        monkeypatch.setattr(
            "teaching_agent.tools.case_design.httpx.AsyncClient", _FakeAsyncClient
        )

    return _install


@pytest.mark.asyncio
async def test_save_case_draft_success(fake_http):
    fake_http(
        200,
        {"project_id": "abc", "project_name": "案例A", "stage_count": 2, "created": True},
    )
    tool = create_save_case_draft_tool()
    result = json.loads(
        await tool.ainvoke(
            {
                "name": "案例A",
                "background_md": "背景",
                "objective": "目标",
                "stages": [{"title": "阶段一"}, {"title": "阶段二"}],
            }
        )
    )
    assert result["ok"] is True
    assert result["project_id"] == "abc"
    assert result["url"] == "/teacher/manage/projects/abc/edit"
    sent = _FakeAsyncClient.calls[0]["json"]
    assert sent["project_id"] is None
    assert sent["stages"][0]["title"] == "阶段一"


@pytest.mark.asyncio
async def test_save_case_draft_name_conflict(fake_http):
    fake_http(
        409,
        {
            "detail": {
                "error": {
                    "code": "PROJECT_NAME_CONFLICT",
                    "message": "案例名称「案例A」已存在，请换一个名称",
                }
            }
        },
    )
    tool = create_save_case_draft_tool()
    result = json.loads(
        await tool.ainvoke(
            {
                "name": "案例A",
                "background_md": "背景",
                "objective": "目标",
                "stages": [{"title": "阶段一"}],
            }
        )
    )
    assert result["ok"] is False
    assert "已存在" in result["error"]

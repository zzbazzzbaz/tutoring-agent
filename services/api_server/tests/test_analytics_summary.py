# 统计分析--LLM 研究摘要（P1-5.4）测试
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from tutoring.analytics import router as analytics_router
from tutoring.analytics import summary as analytics_summary
from tutoring.analytics.schemas import (
    DashboardOverview,
    DashboardResponse,
    MessageStats,
)
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError


def _teacher() -> CurrentUser:
    return CurrentUser(id=uuid4(), username="teacher", role="teacher", name="Teacher")


def _dashboard_stub() -> DashboardResponse:
    """结构完整的 Dashboard 桩，供 generate_summary 消费。"""
    return DashboardResponse(
        overview=DashboardOverview(
            total_students=10,
            active_today=3,
            total_sessions=20,
            pending_alert_count=1,
        ),
        anomalies=[],
        trend=[],
        class_comparison=[],
        mode_distribution=[],
        student_ranking=[],
        message_stats=MessageStats(
            total_messages=6,
            student_messages=3,
            assistant_messages=3,
            avg_turns=1.5,
            knowledge_hit_rate=0.67,
        ),
        key_students=[],
    )


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data):
        self._data = data
        self.posted = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def post(self, url, headers, json):
        self.posted = (url, headers, json)
        return _FakeResp(self._data)


# === generate_summary 降级 ===


@pytest.mark.asyncio
async def test_generate_summary_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    with pytest.raises(analytics_summary.SummaryUnavailable):
        await analytics_summary.generate_summary(_dashboard_stub())


@pytest.mark.asyncio
async def test_generate_summary_placeholder_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("你的阿里云DashScope_API_Key"))
    with pytest.raises(analytics_summary.SummaryUnavailable):
        await analytics_summary.generate_summary(_dashboard_stub())


@pytest.mark.asyncio
async def test_generate_summary_success(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("sk-real-abc123"))
    monkeypatch.setattr(settings, "llm_model", "qwen3.7-flash")
    monkeypatch.setattr(settings, "dashscope_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    fake = _FakeClient({"choices": [{"message": {"content": "AI 研究摘要内容"}}]})
    monkeypatch.setattr(analytics_summary.httpx, "AsyncClient", lambda **kw: fake)

    text = await analytics_summary.generate_summary(_dashboard_stub())
    assert text == "AI 研究摘要内容"
    assert fake.posted is not None
    assert "Authorization" in fake.posted[1]
    assert fake.posted[1]["Authorization"] == "Bearer sk-real-abc123"


@pytest.mark.asyncio
async def test_generate_summary_empty_content_raises(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("sk-real-abc123"))
    fake = _FakeClient({"choices": [{"message": {"content": "  "}}]})
    monkeypatch.setattr(analytics_summary.httpx, "AsyncClient", lambda **kw: fake)
    with pytest.raises(analytics_summary.SummaryUnavailable):
        await analytics_summary.generate_summary(_dashboard_stub())


@pytest.mark.asyncio
async def test_generate_summary_http_error_raises(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("sk-real-abc123"))

    class _ErrResp(_FakeResp):
        def raise_for_status(self):
            raise RuntimeError("500")

    fake = _FakeClient(_ErrResp({}))
    monkeypatch.setattr(analytics_summary.httpx, "AsyncClient", lambda **kw: fake)
    with pytest.raises(analytics_summary.SummaryUnavailable):
        await analytics_summary.generate_summary(_dashboard_stub())


# === 路由：GET /analytics/dashboard/summary ===


def _patch_dashboard(monkeypatch):
    """mock get_dashboard，避免路由真实查询数据库。"""

    async def fake_get_dashboard(_db, _teacher_id, class_id, days):
        return _dashboard_stub()

    monkeypatch.setattr(analytics_router.analytics_service, "get_dashboard", fake_get_dashboard)


@pytest.mark.asyncio
async def test_summary_route_success(monkeypatch):
    _patch_dashboard(monkeypatch)

    async def fake_generate(_dashboard):
        return "AI 研究摘要内容"

    monkeypatch.setattr(analytics_summary, "generate_summary", fake_generate)

    resp = await analytics_router.get_dashboard_summary(
        class_id=None, days=30, user=_teacher(), db=object()
    )
    assert resp.summary == "AI 研究摘要内容"
    assert resp.source == "llm"


@pytest.mark.asyncio
async def test_summary_route_unavailable_returns_503(monkeypatch):
    _patch_dashboard(monkeypatch)

    async def fake_fail(_dashboard):
        raise analytics_summary.SummaryUnavailable("no key")

    monkeypatch.setattr(analytics_summary, "generate_summary", fake_fail)

    with pytest.raises(AppError) as exc_info:
        await analytics_router.get_dashboard_summary(
            class_id=None, days=30, user=_teacher(), db=object()
        )
    assert exc_info.value.status_code == 503

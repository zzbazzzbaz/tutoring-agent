# 平时分（AI 评分）测试
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from docx import Document
from pydantic import SecretStr

from tutoring.analytics import export as analytics_export
from tutoring.analytics import router as analytics_router
from tutoring.analytics import scoring_service
from tutoring.analytics.schemas import ScoringResultResponse, StudentScoreItem
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import ScoringPrompt, StudentScore


def test_scoring_prompt_table_name():
    assert ScoringPrompt.__tablename__ == "scoring_prompt"


def test_student_score_table_name():
    assert StudentScore.__tablename__ == "student_score"


@pytest.mark.asyncio
async def test_upsert_scoring_prompt_insert():
    """不存在时插入新行。"""
    calls: list[str] = []

    class FakeSession:
        def add(self, obj):
            calls.append("add")

        async def execute(self, _stmt):
            class R:
                def scalar_one_or_none(self):
                    return None

            return R()

        async def commit(self):
            calls.append("commit")

        async def refresh(self, obj):
            calls.append("refresh")

    row = await repos.upsert_scoring_prompt(FakeSession(), uuid4(), "标准")
    assert isinstance(row, ScoringPrompt)
    assert calls == ["add", "commit", "refresh"]


@pytest.mark.asyncio
async def test_upsert_scoring_prompt_update():
    """已存在时更新 prompt 字段，不新增行。"""
    existing = ScoringPrompt(id=uuid4(), teacher_id=uuid4(), prompt="旧")

    class FakeSession:
        def add(self, obj):
            raise AssertionError("不应新增行")

        async def execute(self, _stmt):
            class R:
                def scalar_one_or_none(self):
                    return existing

            return R()

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    row = await repos.upsert_scoring_prompt(FakeSession(), existing.teacher_id, "新")
    assert row is existing
    assert row.prompt == "新"


@pytest.mark.asyncio
async def test_list_class_student_usage_empty_class():
    """班级无学生时直接返回 []，不执行第二条聚合查询。"""

    class FakeResult:
        def all(self):
            return []

    class FakeSession:
        async def execute(self, _stmt):
            return FakeResult()

    rows = await repos.list_class_student_usage(FakeSession(), class_id=uuid4())
    assert rows == []


# === scoring_service ===


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, content):
        self._content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def post(self, url, headers, json):
        return _FakeResp({"choices": [{"message": {"content": self._content}}]})


def _usage_rows():
    return [
        {
            "user_id": uuid4(),
            "name": "张三",
            "username": "001",
            "sessions": 10,
            "student_messages": 50,
            "active_days": 5,
            "knowledge_hits": 30,
            "last_active_at": datetime(2026, 10, 1, tzinfo=UTC),
        },
        {
            "user_id": uuid4(),
            "name": "李四",
            "username": "002",
            "sessions": 0,
            "student_messages": 0,
            "active_days": 0,
            "knowledge_hits": 0,
            "last_active_at": None,
        },
    ]


def test_parse_scores_success():
    text = (
        '```json\n[{"index": 1, "score": 85, "reason": "活跃"}, '
        '{"index": 2, "score": 40, "reason": "少用"}]\n```'
    )
    rows = _usage_rows()
    result = scoring_service._parse_scores(text, rows)
    assert result == [
        {"student_id": rows[0]["user_id"], "score": 85, "reason": "活跃"},
        {"student_id": rows[1]["user_id"], "score": 40, "reason": "少用"},
    ]


def test_parse_scores_clamps_and_ignores_noise():
    text = (
        '以下是评分：\n[{"index": 1, "score": 130, "reason": ""}, '
        '{"index": 2, "score": -5}]\n请查收'
    )
    result = scoring_service._parse_scores(text, _usage_rows())
    assert [r["score"] for r in result] == [100, 0]
    assert result[1]["reason"] == ""


def test_parse_scores_missing_index_raises():
    text = '[{"index": 1, "score": 80, "reason": "a"}]'
    with pytest.raises(scoring_service.ScoringUnavailable):
        scoring_service._parse_scores(text, _usage_rows())


def test_render_usage_table_renders_zero_for_unused_student():
    table = scoring_service._render_usage_table(_usage_rows(), {})
    lines = table.splitlines()
    assert lines[0].startswith("行号")
    assert "张三" in lines[1] and "60%" in lines[1]
    assert "李四" in lines[2] and "-" in lines[2]


@pytest.mark.asyncio
async def test_generate_scores_missing_key_raises(monkeypatch):
    rows = _usage_rows()

    async def fake_usage(_db, *, class_id, since=None):
        return rows

    async def fake_project(_db, *, class_id):
        return {}

    async def fake_prompt(_db, _teacher_id):
        return None

    monkeypatch.setattr(repos, "list_class_student_usage", fake_usage)
    monkeypatch.setattr(repos, "get_class_student_project_stats", fake_project)
    monkeypatch.setattr(repos, "get_scoring_prompt", fake_prompt)
    monkeypatch.setattr(settings, "dashscope_api_key", None)

    teacher_id = uuid4()
    cls = SimpleNamespace(
        id=uuid4(),
        grade="2025级",
        classname="1班",
        teacher_id=teacher_id,
        deleted_at=None,
        status="active",
    )

    class FakeDB:
        async def get(self, _model, _class_id):
            return cls

    with pytest.raises(scoring_service.ScoringUnavailable):
        await scoring_service.generate_scores(FakeDB(), teacher_id, cls.id)


@pytest.mark.asyncio
async def test_generate_scores_success_persists(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("sk-real-abc123"))
    monkeypatch.setattr(settings, "llm_model", "qwen3.7-flash")
    monkeypatch.setattr(
        settings, "dashscope_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    rows = _usage_rows()
    saved: dict = {}

    async def fake_usage(_db, *, class_id, since=None):
        return rows

    async def fake_project(_db, *, class_id):
        return {}

    async def fake_prompt(_db, _teacher_id):
        return None

    async def fake_replace(_db, class_id, orm_rows):
        saved["rows"] = orm_rows

    monkeypatch.setattr(repos, "list_class_student_usage", fake_usage)
    monkeypatch.setattr(repos, "get_class_student_project_stats", fake_project)
    monkeypatch.setattr(repos, "get_scoring_prompt", fake_prompt)
    monkeypatch.setattr(repos, "replace_class_student_scores", fake_replace)

    content = (
        '[{"index": 1, "score": 85, "reason": "活跃"}, {"index": 2, "score": 40, "reason": "少用"}]'
    )
    monkeypatch.setattr(scoring_service.httpx, "AsyncClient", lambda **kw: _FakeClient(content))

    cls = SimpleNamespace(
        id=uuid4(), grade="2025级", classname="1班", teacher_id=None,
        deleted_at=None, status="active",
    )

    class FakeDB:
        async def get(self, _model, _class_id):
            return cls

    teacher_id = uuid4()
    cls.teacher_id = teacher_id
    result = await scoring_service.generate_scores(FakeDB(), teacher_id, cls.id)
    assert [i.score for i in result.items] == [85, 40]
    assert len(saved["rows"]) == 2
    assert saved["rows"][0].metrics["knowledge_hit_rate"] == 0.6


# === 路由 ===


def _teacher():
    return CurrentUser(id=uuid4(), username="t", role="teacher", name="T")


def _patch_scoring_deps(monkeypatch, *, prompt_row=None, scores=None):
    async def fake_get_prompt(_db, _teacher_id):
        return prompt_row

    async def fake_list_scores(_db, _class_id):
        return scores or []

    monkeypatch.setattr(analytics_router.repos, "get_scoring_prompt", fake_get_prompt)
    monkeypatch.setattr(analytics_router.repos, "list_class_student_scores", fake_list_scores)


@pytest.mark.asyncio
async def test_scoring_prompt_default(monkeypatch):
    _patch_scoring_deps(monkeypatch)
    resp = await analytics_router.get_scoring_prompt(user=_teacher(), db=object())
    assert resp.is_default is True
    assert resp.prompt == analytics_router.scoring_service.DEFAULT_SCORING_PROMPT


@pytest.mark.asyncio
async def test_scoring_prompt_update(monkeypatch):
    saved = {}

    async def fake_upsert(_db, teacher_id, prompt):
        saved["prompt"] = prompt

    monkeypatch.setattr(analytics_router.repos, "upsert_scoring_prompt", fake_upsert)
    resp = await analytics_router.update_scoring_prompt(
        body=analytics_router.ScoringPromptUpdate(prompt="自定义标准"),
        user=_teacher(),
        db=object(),
    )
    assert resp.is_default is False
    assert saved["prompt"] == "自定义标准"


@pytest.mark.asyncio
async def test_scoring_generate_unavailable_returns_503(monkeypatch):
    async def fake_generate(_db, _teacher_id, _class_id, _since):
        raise analytics_router.scoring_service.ScoringUnavailable("no key")

    monkeypatch.setattr(analytics_router.scoring_service, "generate_scores", fake_generate)
    with pytest.raises(AppError) as exc_info:
        await analytics_router.generate_scoring(
            body=analytics_router.ScoringGenerateRequest(class_id=uuid4(), since=None),
            user=_teacher(),
            db=object(),
        )
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_scoring_get_empty(monkeypatch):
    teacher = _teacher()

    class FakeDB:
        async def get(self, _model, _class_id):
            return SimpleNamespace(
                id=uuid4(), teacher_id=teacher.id, grade="2025级", classname="1班",
                deleted_at=None, status="active",
            )

    async def fake_list_scores(_db, _class_id):
        return []

    monkeypatch.setattr(analytics_router.repos, "list_class_student_scores", fake_list_scores)

    db = FakeDB()
    cls = await db.get(None, None)
    resp = await analytics_router.get_scoring(class_id=cls.id, user=teacher, db=db)
    assert resp.items == []
    assert resp.generated_at is None


# === 导出 ===


def test_build_scoring_docx_contains_rows():
    result = ScoringResultResponse(
        class_id=uuid4(),
        class_name="2025级 1班",
        since=None,
        generated_at=datetime.now(UTC),
        items=[
            StudentScoreItem(
                student_id=uuid4(), name="张三", username="001", score=85, reason="使用活跃"
            ),
        ],
    )
    buf = analytics_export.build_scoring_docx(result=result, generated_at=datetime.now(UTC))
    doc = Document(buf)
    texts = "\n".join(p.text for p in doc.paragraphs) + "\n".join(
        cell.text for t in doc.tables for row in t.rows for cell in row.cells
    )
    assert "平时分" in texts
    assert "张三" in texts
    assert "85" in texts

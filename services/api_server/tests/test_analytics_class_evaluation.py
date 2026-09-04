# 统计分析--班级评价（P2-阶段②）service 层测试
# 结构：ClassEvaluationResponse.classes[]（指定班级=1 项，全部班级=N 项逐班独立计算）
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.analytics import service as analytics_service
from tutoring.db import repos as repos_module


class _FakeDB:
    """mock db：get(Class) 返回给定班级或 None。"""

    def __init__(self, cls):
        self.cls = cls

    async def get(self, _model, class_id):
        return self.cls if self.cls is not None and self.cls.id == class_id else None


def _patch_repos(monkeypatch, *, stats=None, thinking=None, classes=None, progress=None, subject=None):
    """替换 get_class_evaluation 依赖的 repos 函数。

    stats/thinking/subject 可传 dict（所有班级一致）或 callable(class_ids, since)->dict（按班级区分）；
    progress 为 list_project_progress_summary 的 mock 返回值（默认 []）。
    """

    async def fake_list_classes_by_teacher(_db, _teacher_id):
        return classes or []

    async def fake_get_class_participation_stats(_db, class_ids, since):
        if callable(stats):
            return stats(class_ids, since)
        return stats if stats is not None else {}

    async def fake_get_class_thinking_stats(_db, class_ids, since):
        if callable(thinking):
            return thinking(class_ids, since)
        return thinking if thinking is not None else _thinking()

    async def fake_list_project_progress_summary(_db, class_ids):
        return progress if progress is not None else []

    async def fake_get_class_subject_stats(_db, class_ids, since):
        if callable(subject):
            return subject(class_ids, since)
        return subject if subject is not None else _subject()

    monkeypatch.setattr(repos_module, "list_classes_by_teacher", fake_list_classes_by_teacher)
    monkeypatch.setattr(
        repos_module, "get_class_participation_stats", fake_get_class_participation_stats
    )
    monkeypatch.setattr(
        repos_module, "get_class_thinking_stats", fake_get_class_thinking_stats
    )
    monkeypatch.setattr(
        repos_module, "list_project_progress_summary", fake_list_project_progress_summary
    )
    monkeypatch.setattr(
        repos_module, "get_class_subject_stats", fake_get_class_subject_stats
    )


def _stats(**overrides):
    base = {
        "total_students": 10,
        "active_students": 8,
        "sessions": 20,
        "active_days": 5,
        "student_messages": 100,
    }
    base.update(overrides)
    return base


def _thinking(**overrides):
    base = {
        "student_messages": 10,
        "deep_questions": 5,
        "follow_up_messages": 4,
        "knowledge_hit_count": 6,
        "assistant_messages": 12,
        "sessions_with_messages": 4,
    }
    base.update(overrides)
    return base


def _subject(**overrides):
    base = {
        "project_students": 0,
        "student_doc_counts": {},
        "class_doc_count": 0,
    }
    base.update(overrides)
    return base


def _make_class(teacher_id, classname="一班"):
    return SimpleNamespace(
        id=uuid4(), grade="大一", classname=classname, deleted_at=None, status="active", teacher_id=teacher_id
    )


def _stage(
    has_deliverable,
    submitted=0,
    done=0,
    completed=0,
    in_progress=0,
    started=0,
    deliverable_title=None,
):
    return {
        "stage_id": "stg_x",
        "order": 1,
        "title": "阶段",
        "has_deliverable": has_deliverable,
        "deliverable_title": (
            deliverable_title
            if deliverable_title is not None
            else ("产出物" if has_deliverable else None)
        ),
        "completed_count": completed,
        "in_progress_count": in_progress,
        "started_count": started,
        "deliverable_submitted_count": submitted,
        "deliverable_done_count": done,
    }


def _project(student_count, stages):
    return {
        "project_id": uuid4(),
        "project_name": "项目",
        "student_count": student_count,
        "stage_count": len(stages),
        "stages": stages,
    }


def _get_dimension(item, dimension_id):
    dims = [d for d in item.dimensions if d.dimension_id == dimension_id]
    assert len(dims) == 1, f"期望 1 个 {dimension_id} 维度，实际 {len(dims)}"
    return dims[0]


# === 指定班级：单班六维 ===

@pytest.mark.asyncio
async def test_class_evaluation_participation_high(monkeypatch):
    """指定班级：参与度高分场景（全活跃 + 会话/消息达标）→ score=100 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(total_students=10, active_students=10, sessions=100, student_messages=600),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    assert data.days == 30
    assert len(data.classes) == 1
    item = data.classes[0]
    assert item.class_id == cls.id
    assert item.class_name == "大一 一班"
    assert len(item.dimensions) == 6
    dim = _get_dimension(item, "participation")
    assert dim.score == 100
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["活跃天数"] == "5"
    assert labels["会话数"] == "100"
    assert labels["学生发起消息"] == "600"
    assert labels["活跃学生"] == "10/10"
    # 思考质量/知识运用/产出物完成/阶段覆盖/学科维度也应存在
    assert _get_dimension(item, "thinking").dimension_id == "thinking"
    assert _get_dimension(item, "knowledge").dimension_id == "knowledge"
    assert _get_dimension(item, "deliverable").dimension_id == "deliverable"
    assert _get_dimension(item, "stage_coverage").dimension_id == "stage_coverage"
    assert _get_dimension(item, "subject").dimension_id == "subject"


@pytest.mark.asyncio
async def test_class_evaluation_participation_mid(monkeypatch):
    """参与度中等场景（复合分 0.64）→ score=64 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(total_students=10, active_students=7, sessions=40, student_messages=120),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=7)

    item = data.classes[0]
    dim = _get_dimension(item, "participation")
    # 0.7*0.4 + min(40/10/5,1)*0.3 + min(120/10/30,1)*0.3 = 0.28 + 0.24 + 0.12 = 0.64 → 64
    assert dim.score == 64
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_participation_low(monkeypatch):
    """参与度低分场景 → score=54 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(total_students=10, active_students=8, sessions=20, student_messages=100),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "participation")
    # 0.8*0.4 + min(20/10/5,1)*0.3 + min(100/10/30,1)*0.3 = 0.32 + 0.12 + 0.1 = 0.54 → 54
    assert dim.score == 54
    assert dim.level == "低"


@pytest.mark.asyncio
async def test_class_evaluation_zero_students(monkeypatch):
    """班级无学生时参与度 score=0 等级低，不抛错。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, stats=_stats(total_students=0))

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "participation")
    assert dim.score == 0
    assert dim.level == "低"


# === 全部班级：逐班独立计算（方案 A，横向对比）===

@pytest.mark.asyncio
async def test_class_evaluation_all_classes_independent(monkeypatch):
    """全部班级：每个班级按自己的数据独立计算六维，互不影响（不做混算）。"""
    teacher_id = uuid4()
    cls1 = _make_class(teacher_id, classname="一班")
    cls2 = _make_class(teacher_id, classname="二班")
    db = _FakeDB(None)

    def stats_for(class_ids, _since):
        # cls1 参与度满分；cls2 参与度低分
        if class_ids == [cls1.id]:
            return _stats(total_students=10, active_students=10, sessions=100, student_messages=600)
        return _stats(total_students=10, active_students=2, sessions=3, student_messages=5)

    def thinking_for(class_ids, _since):
        # cls1 思考质量满分；cls2 思考质量 0（无提问）
        if class_ids == [cls1.id]:
            return _thinking(
                student_messages=10,
                deep_questions=10,
                follow_up_messages=10,
                knowledge_hit_count=10,
                assistant_messages=25,
                sessions_with_messages=5,
            )
        return _thinking(
            student_messages=0,
            deep_questions=0,
            follow_up_messages=0,
            knowledge_hit_count=0,
            assistant_messages=0,
            sessions_with_messages=0,
        )

    _patch_repos(monkeypatch, stats=stats_for, thinking=thinking_for, classes=[cls1, cls2])

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=None, days=30)

    assert data.days == 30
    assert len(data.classes) == 2
    item1, item2 = data.classes
    assert item1.class_id == cls1.id and item1.class_name == "大一 一班"
    assert item2.class_id == cls2.id and item2.class_name == "大一 二班"
    # cls1：三维满分
    assert _get_dimension(item1, "participation").score == 100
    assert _get_dimension(item1, "thinking").score == 100
    assert _get_dimension(item1, "knowledge").score == 100
    # cls2：低分/0（独立计算，未与 cls1 混算）
    p2 = _get_dimension(item2, "participation")
    # 0.2*0.4 + min(3/10/5,1)*0.3 + min(5/10/30,1)*0.3 ≈ 0.08+0.018+0.005 ≈ 0.103 → 10
    assert p2.score == 10
    assert p2.level == "低"
    assert _get_dimension(item2, "thinking").score == 0
    assert _get_dimension(item2, "knowledge").score == 0


@pytest.mark.asyncio
async def test_class_evaluation_empty_class(monkeypatch):
    """班级不存在/不属于该教师时返回空 classes。"""
    teacher_id = uuid4()
    db = _FakeDB(None)

    _patch_repos(monkeypatch, stats=_stats())

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=uuid4(), days=30)

    assert data.classes == []


@pytest.mark.asyncio
async def test_class_evaluation_no_classes(monkeypatch):
    """教师没有任何班级时返回空 classes。"""
    teacher_id = uuid4()
    db = _FakeDB(None)

    _patch_repos(monkeypatch, stats=_stats(), classes=[])

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=None, days=30)

    assert data.classes == []


# === P2-阶段②-2 思考质量维度 ===

@pytest.mark.asyncio
async def test_class_evaluation_thinking_high(monkeypatch):
    """思考质量高分场景：深度/追问/命中/轮次均达标 → score=100 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            deep_questions=10,
            follow_up_messages=10,
            knowledge_hit_count=10,
            assistant_messages=25,
            sessions_with_messages=5,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "thinking")
    assert dim.name == "思考质量"
    # 深度=1.0 追问=1.0 命中=1.0 轮次=min(25/5/5,1)=1.0 → 1.0*0.3+1.0*0.25+1.0*0.25+1.0*0.2=1.0 → 100
    assert dim.score == 100
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["学生提问"] == "10"
    assert labels["深度提问"] == "10"
    assert labels["主动追问"] == "10"
    assert labels["知识命中率"] == "100%"
    assert labels["平均轮次"] == "5.0"


@pytest.mark.asyncio
async def test_class_evaluation_thinking_mid(monkeypatch):
    """思考质量中等场景（复合分 0.68）→ score=68 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            deep_questions=7,   # 0.7 → 0.21
            follow_up_messages=7,  # 0.7 → 0.175
            knowledge_hit_count=7,  # 0.7 → 0.175
            assistant_messages=15,  # 轮次=min(15/5/5,1)=0.6 → 0.12
            sessions_with_messages=5,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "thinking")
    # 0.7*0.3 + 0.7*0.25 + 0.7*0.25 + 0.6*0.2 = 0.21+0.175+0.175+0.12 = 0.68 → 68
    assert dim.score == 68
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_thinking_zero_students(monkeypatch):
    """无学生提问时思考质量 score=0 等级低，不抛错。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=0,
            deep_questions=0,
            follow_up_messages=0,
            knowledge_hit_count=0,
            assistant_messages=0,
            sessions_with_messages=0,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "thinking")
    assert dim.score == 0
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["知识命中率"] == "0%"
    assert labels["平均轮次"] == "0.0"


@pytest.mark.asyncio
async def test_class_evaluation_thinking_full_saturation(monkeypatch):
    """思考质量各子项封顶：人均轮次远超 5 仍为 100（不溢出）。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            deep_questions=10,
            follow_up_messages=10,
            knowledge_hit_count=10,
            assistant_messages=1000,  # 人均轮次远大于 5
            sessions_with_messages=5,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "thinking")
    assert dim.score == 100
    assert dim.level == "高"


# === P2-阶段②-3 知识运用维度 ===

@pytest.mark.asyncio
async def test_class_evaluation_knowledge_high(monkeypatch):
    """知识运用高分场景：命中 8/10 → score=80 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            knowledge_hit_count=8,
            deep_questions=0,
            follow_up_messages=0,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "knowledge")
    assert dim.name == "知识运用"
    assert dim.score == 80
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["学生提问"] == "10"
    assert labels["命中提问"] == "8"
    assert labels["知识命中率"] == "80%"


@pytest.mark.asyncio
async def test_class_evaluation_knowledge_mid(monkeypatch):
    """知识运用中等场景：命中 6/10 → score=60 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            knowledge_hit_count=6,
            deep_questions=0,
            follow_up_messages=0,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "knowledge")
    assert dim.score == 60
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_knowledge_low(monkeypatch):
    """知识运用低分场景：命中 1/10 → score=10 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=10,
            knowledge_hit_count=1,
            deep_questions=0,
            follow_up_messages=0,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "knowledge")
    assert dim.score == 10
    assert dim.level == "低"


@pytest.mark.asyncio
async def test_class_evaluation_knowledge_zero_students(monkeypatch):
    """无学生提问时知识运用 score=0 等级低，不抛错。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        stats=_stats(),
        thinking=_thinking(
            student_messages=0,
            knowledge_hit_count=0,
            deep_questions=0,
            follow_up_messages=0,
            assistant_messages=0,
            sessions_with_messages=0,
        ),
    )

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "knowledge")
    assert dim.score == 0
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["知识命中率"] == "0%"


# === P2-阶段②-4 产出物完成维度 ===

@pytest.mark.asyncio
async def test_class_evaluation_deliverable_high(monkeypatch):
    """产出物完成高分场景：提交率 100% + 达标率 100% → score=100 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # 4 学生 × 2 个含产出物阶段 = 可提交 8；全部提交且达标
    progress = [
        _project(
            student_count=4,
            stages=[_stage(True, submitted=4, done=4), _stage(True, submitted=4, done=4)],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "deliverable")
    assert dim.name == "产出物完成"
    assert dim.score == 100
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "1"
    assert labels["可提交条目"] == "8"
    assert labels["已提交条目"] == "8"
    assert labels["已达标条目"] == "8"
    assert labels["提交率"] == "100%"
    assert labels["达标率"] == "100%"


@pytest.mark.asyncio
async def test_class_evaluation_deliverable_mid(monkeypatch):
    """产出物完成中等场景：提交 6/10、达标 5/6 → 复合 0.7167 → score=72 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # 5 学生 × 2 个含产出物阶段 = 可提交 10；提交 6，达标 5
    progress = [
        _project(
            student_count=5,
            stages=[_stage(True, submitted=3, done=3), _stage(True, submitted=3, done=2)],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "deliverable")
    # 提交率=0.6 达标率=5/6≈0.8333 → (0.6+0.8333)/2 ≈ 0.7167 → 71.67 → round=72
    assert dim.score == 72
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_deliverable_zero(monkeypatch):
    """无可提交条目（无项目/无参与学生）时产出物完成 score=0 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, stats=_stats(), progress=[])

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "deliverable")
    assert dim.score == 0
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "0"
    assert labels["可提交条目"] == "0"
    assert labels["提交率"] == "0%"
    assert labels["达标率"] == "0%"


@pytest.mark.asyncio
async def test_class_evaluation_deliverable_excludes_inactive_projects(monkeypatch):
    """未启动项目（student_count=0）不计入可提交条目与参与项目数。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    progress = [
        # 参与项目：3 学生 × 2 个含产出物阶段 = 可提交 6；提交 3、达标 3
        _project(
            student_count=3,
            stages=[_stage(True, submitted=2, done=2), _stage(True, submitted=1, done=1)],
        ),
        # 未启动项目：student_count=0，应被排除（即使含产出物阶段）
        _project(student_count=0, stages=[_stage(True), _stage(True), _stage(True)]),
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "deliverable")
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "1"
    assert labels["可提交条目"] == "6"
    assert labels["已提交条目"] == "3"
    assert labels["已达标条目"] == "3"
    # 提交率=0.5 达标率=1.0 → (0.5+1.0)/2 = 0.75 → 75
    assert dim.score == 75
    assert dim.level == "中"


# === P2-阶段②-5 阶段覆盖维度 ===

@pytest.mark.asyncio
async def test_class_evaluation_stage_coverage_high(monkeypatch):
    """阶段覆盖高分场景：完成率 100% + 覆盖率 100% → score=100 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # 4 学生 × 2 阶段 = 应覆盖 8；全部完成（completed=8, started=8）
    progress = [
        _project(
            student_count=4,
            stages=[
                _stage(has_deliverable=True, completed=4, started=4),
                _stage(has_deliverable=False, completed=4, started=4),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "stage_coverage")
    assert dim.name == "阶段覆盖"
    # 完成率=1.0 覆盖率=1.0 → 1.0*0.7 + 1.0*0.3 = 1.0 → 100
    assert dim.score == 100
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "1"
    assert labels["参与学生"] == "4"
    assert labels["应覆盖条目"] == "8"
    assert labels["已开始条目"] == "8"
    assert labels["已完成条目"] == "8"
    assert labels["阶段完成率"] == "100%"
    assert labels["阶段覆盖率"] == "100%"


@pytest.mark.asyncio
async def test_class_evaluation_stage_coverage_mid(monkeypatch):
    """阶段覆盖中等场景：完成率 70% + 覆盖率 100% → 复合 0.79 → score=79 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # 4 学生 × 5 阶段 = 应覆盖 20；完成 14、已开始 20
    progress = [
        _project(
            student_count=4,
            stages=[
                _stage(has_deliverable=True, completed=4, started=4),
                _stage(has_deliverable=True, completed=4, started=4),
                _stage(has_deliverable=False, completed=3, started=4),
                _stage(has_deliverable=False, completed=2, started=4),
                _stage(has_deliverable=False, completed=1, started=4),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "stage_coverage")
    # 完成率=14/20=0.7 覆盖率=20/20=1.0 → 0.7*0.7 + 1.0*0.3 = 0.79 → 79
    assert dim.score == 79
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_stage_coverage_zero(monkeypatch):
    """无参与项目（无项目/无参与学生）时阶段覆盖 score=0 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, stats=_stats(), progress=[])

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "stage_coverage")
    assert dim.score == 0
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "0"
    assert labels["应覆盖条目"] == "0"
    assert labels["阶段完成率"] == "0%"
    assert labels["阶段覆盖率"] == "0%"


@pytest.mark.asyncio
async def test_class_evaluation_stage_coverage_excludes_inactive_projects(monkeypatch):
    """未启动项目（student_count=0）不计入应覆盖条目与参与项目数。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    progress = [
        # 参与项目：3 学生 × 2 阶段 = 应覆盖 6；完成 4、已开始 5
        _project(
            student_count=3,
            stages=[
                _stage(has_deliverable=True, completed=3, in_progress=0, started=3),
                _stage(has_deliverable=False, completed=1, in_progress=1, started=2),
            ],
        ),
        # 未启动项目：student_count=0，应被排除（即使有阶段定义）
        _project(student_count=0, stages=[_stage(True), _stage(True), _stage(True)]),
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "stage_coverage")
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["参与项目"] == "1"
    assert labels["参与学生"] == "3"
    assert labels["应覆盖条目"] == "6"
    assert labels["已开始条目"] == "5"
    assert labels["已完成条目"] == "4"
    # 完成率=4/6≈0.6667 覆盖率=5/6≈0.8333 → 0.4667+0.25 ≈ 0.7167 → 72
    assert dim.score == 72
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_stage_coverage_weight(monkeypatch):
    """阶段覆盖权重验证：仅覆盖（完成率 0%、覆盖率 100%）→ 30 分，体现 70/30 权重。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # 2 学生 × 2 阶段 = 应覆盖 4；全部已开始但无人完成
    progress = [
        _project(
            student_count=2,
            stages=[
                _stage(has_deliverable=True, completed=0, in_progress=2, started=2),
                _stage(has_deliverable=False, completed=0, in_progress=2, started=2),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "stage_coverage")
    # 完成率=0 覆盖率=1.0 → 0*0.7 + 1.0*0.3 = 0.3 → 30
    assert dim.score == 30
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["阶段完成率"] == "0%"
    assert labels["阶段覆盖率"] == "100%"


# === P2-阶段②-6 学科维度 ===

@pytest.mark.asyncio
async def test_class_evaluation_subject_high(monkeypatch):
    """学科维度高分场景：知识点覆盖 100% + 案例分析 100% + 情境应用 100% → score=100 等级高。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # ① 4 学生每人命中相同 5 文档 → 人均 5/全班 5 = 100%
    subject = _subject(
        project_students=4,
        student_doc_counts={"u1": 5, "u2": 5, "u3": 5, "u4": 5},
        class_doc_count=5,
    )
    # ②③ 案例类/方案类全部提交且达标 → 100%
    progress = [
        _project(
            student_count=4,
            stages=[
                _stage(has_deliverable=True, submitted=4, done=4, deliverable_title="焦虑行为观察记录"),
                _stage(has_deliverable=True, submitted=4, done=4, deliverable_title="个别化引导方案"),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress, subject=subject)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "subject")
    assert dim.name == "学科"
    # 1.0*0.4 + 1.0*0.3 + 1.0*0.3 = 1.0 → 100
    assert dim.score == 100
    assert dim.level == "高"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["命中涉及学生"] == "4"
    assert labels["命中文档(全班)"] == "5"
    assert labels["知识点覆盖"] == "100%"
    assert labels["案例类提交"] == "4"
    assert labels["案例类达标"] == "4"
    assert labels["案例分析达标率"] == "100%"
    assert labels["方案类提交"] == "4"
    assert labels["方案类达标"] == "4"
    assert labels["情境应用达标率"] == "100%"


@pytest.mark.asyncio
async def test_class_evaluation_subject_mid(monkeypatch):
    """学科维度中等场景：覆盖 50% + 案例分析 80% + 情境应用 60% → 复合 0.62 → score=62 等级中。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # ① 人均 = (3+3+2+2)/4 = 2.5，全班去重 5 → 50%
    subject = _subject(
        project_students=4,
        student_doc_counts={"u1": 3, "u2": 3, "u3": 2, "u4": 2},
        class_doc_count=5,
    )
    progress = [
        _project(
            student_count=4,
            stages=[
                # 案例类：提交 5 达标 4 → 80%
                _stage(has_deliverable=True, submitted=5, done=4, deliverable_title="焦虑行为观察记录"),
                # 方案类：提交 5 达标 3 → 60%
                _stage(has_deliverable=True, submitted=5, done=3, deliverable_title="活动方案"),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress, subject=subject)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "subject")
    # 0.5*0.4 + 0.8*0.3 + 0.6*0.3 = 0.2 + 0.24 + 0.18 = 0.62 → 62
    assert dim.score == 62
    assert dim.level == "中"


@pytest.mark.asyncio
async def test_class_evaluation_subject_zero(monkeypatch):
    """无任何数据（无命中、无提交）时学科维度 score=0 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, stats=_stats(), progress=[], subject=_subject())

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "subject")
    assert dim.score == 0
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["知识点覆盖"] == "0%"
    assert labels["案例分析达标率"] == "0%"
    assert labels["情境应用达标率"] == "0%"


@pytest.mark.asyncio
async def test_class_evaluation_subject_classification(monkeypatch):
    """②③ 标题分类互斥（案例优先）且未启动项目被排除。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    # ① 覆盖 100%（2 学生人均 2 / 全班 2）
    subject = _subject(
        project_students=2,
        student_doc_counts={"u1": 2, "u2": 2},
        class_doc_count=2,
    )
    progress = [
        _project(
            student_count=2,
            stages=[
                # 案例类：提交 2 达标 2
                _stage(has_deliverable=True, submitted=2, done=2, deliverable_title="焦虑行为观察记录"),
                # 方案类：提交 2 达标 1
                _stage(has_deliverable=True, submitted=2, done=1, deliverable_title="个别化引导方案"),
                # 无关键词：不应计入任何类别（即使达标）
                _stage(has_deliverable=True, submitted=2, done=2, deliverable_title="自由任务"),
                # 混合标题：案例优先 → 计入案例类（提交 1 达标 1）
                _stage(has_deliverable=True, submitted=1, done=1, deliverable_title="案例分析方案"),
            ],
        ),
        # 未启动项目：student_count=0，即使标题含案例/方案词也应排除
        _project(
            student_count=0,
            stages=[
                _stage(has_deliverable=True, submitted=99, done=99, deliverable_title="案例分析"),
                _stage(has_deliverable=True, submitted=99, done=99, deliverable_title="设计方案"),
            ],
        ),
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress, subject=subject)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "subject")
    labels = {m.label: m.value for m in dim.metrics}
    # 案例类：2 + 1（混合标题）= 3 提交 3 达标 → 100%
    assert labels["案例类提交"] == "3"
    assert labels["案例类达标"] == "3"
    assert labels["案例分析达标率"] == "100%"
    # 方案类：2 提交 1 达标 → 50%（未混入混合标题、未混入未启动项目）
    assert labels["方案类提交"] == "2"
    assert labels["方案类达标"] == "1"
    assert labels["情境应用达标率"] == "50%"
    # 覆盖 100% → 1.0*0.4 + 1.0*0.3 + 0.5*0.3 = 0.85 → 85
    assert dim.score == 85
    assert dim.level == "高"


@pytest.mark.asyncio
async def test_class_evaluation_subject_no_deliverable_submission(monkeypatch):
    """②③ 无提交时按 0：覆盖 100% + 案例/方案均无提交 → score=40 等级低。"""
    teacher_id = uuid4()
    cls = _make_class(teacher_id)
    db = _FakeDB(cls)

    subject = _subject(
        project_students=2,
        student_doc_counts={"u1": 2, "u2": 2},
        class_doc_count=2,
    )
    progress = [
        _project(
            student_count=2,
            stages=[
                _stage(has_deliverable=True, submitted=0, done=0, deliverable_title="焦虑行为观察记录"),
                _stage(has_deliverable=True, submitted=0, done=0, deliverable_title="活动方案"),
            ],
        )
    ]
    _patch_repos(monkeypatch, stats=_stats(), progress=progress, subject=subject)

    data = await analytics_service.get_class_evaluation(db, teacher_id, class_id=cls.id, days=30)

    item = data.classes[0]
    dim = _get_dimension(item, "subject")
    # 1.0*0.4 + 0 + 0 = 0.4 → 40
    assert dim.score == 40
    assert dim.level == "低"
    labels = {m.label: m.value for m in dim.metrics}
    assert labels["案例分析达标率"] == "0%"
    assert labels["情境应用达标率"] == "0%"

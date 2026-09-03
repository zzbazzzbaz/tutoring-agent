# 统计分析--项目维度进度聚合（P2 阶段①-2）测试
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


def _fake_summary_raw():
    """构造一个项目两条阶段统计的 repos 原始返回。"""
    return [
        {
            "project_id": uuid4(),
            "project_name": "入园适应项目",
            "student_count": 2,
            "stage_count": 2,
            "stages": [
                {
                    "stage_id": "stg_01",
                    "order": 1,
                    "title": "情绪与分离焦虑",
                    "has_deliverable": True,
                    "deliverable_title": "焦虑行为观察记录",
                    "completed_count": 1,
                    "in_progress_count": 1,
                    "started_count": 2,
                    "deliverable_submitted_count": 1,
                    "deliverable_done_count": 1,
                },
                {
                    "stage_id": "stg_02",
                    "order": 2,
                    "title": "注意的稳定性",
                    "has_deliverable": False,
                    "deliverable_title": None,
                    "completed_count": 0,
                    "in_progress_count": 1,
                    "started_count": 1,
                    "deliverable_submitted_count": 0,
                    "deliverable_done_count": 0,
                },
            ],
        }
    ]


def _patch_repos(monkeypatch, *, summary_raw=None, classes=None):
    """替换 get_project_progress_summary 依赖的 repos 函数。"""

    async def fake_list_classes_by_teacher(_db, _teacher_id):
        return classes or []

    async def fake_list_project_progress_summary(_db, class_ids):
        return summary_raw if summary_raw is not None else []

    monkeypatch.setattr(repos_module, "list_classes_by_teacher", fake_list_classes_by_teacher)
    monkeypatch.setattr(repos_module, "list_project_progress_summary", fake_list_project_progress_summary)


@pytest.mark.asyncio
async def test_project_progress_summary_computed(monkeypatch):
    """指定班级：项目与阶段统计按 repos 结果透传组装。"""
    teacher_id = uuid4()
    cls = SimpleNamespace(
        id=uuid4(), grade="大一", classname="一班", deleted_at=None, teacher_id=teacher_id
    )
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, summary_raw=_fake_summary_raw())

    data = await analytics_service.get_project_progress_summary(db, teacher_id, class_id=cls.id)

    assert len(data.projects) == 1
    proj = data.projects[0]
    assert proj.project_name == "入园适应项目"
    assert proj.student_count == 2
    assert proj.stage_count == 2
    s1, s2 = proj.stages
    assert s1.stage_id == "stg_01"
    assert s1.completed_count == 1 and s1.in_progress_count == 1 and s1.started_count == 2
    assert s1.deliverable_title == "焦虑行为观察记录"
    assert s1.deliverable_submitted_count == 1 and s1.deliverable_done_count == 1
    assert s2.has_deliverable is False and s2.deliverable_title is None


@pytest.mark.asyncio
async def test_project_progress_summary_all_classes(monkeypatch):
    """不指定班级时，聚合该教师全部班级（经 list_classes_by_teacher）。"""
    teacher_id = uuid4()
    cls1 = SimpleNamespace(id=uuid4(), grade="大一", classname="一班", deleted_at=None, teacher_id=teacher_id)
    cls2 = SimpleNamespace(id=uuid4(), grade="大二", classname="二班", deleted_at=None, teacher_id=teacher_id)
    db = _FakeDB(cls1)

    _patch_repos(monkeypatch, summary_raw=_fake_summary_raw(), classes=[cls1, cls2])

    data = await analytics_service.get_project_progress_summary(db, teacher_id, class_id=None)

    # repos 已按 class_ids 聚合，service 透传结果
    assert len(data.projects) == 1
    assert data.projects[0].project_name == "入园适应项目"


@pytest.mark.asyncio
async def test_project_progress_summary_empty(monkeypatch):
    """班级内无项目进度时返回空 projects，不抛错。"""
    teacher_id = uuid4()
    cls = SimpleNamespace(
        id=uuid4(), grade="大一", classname="一班", deleted_at=None, teacher_id=teacher_id
    )
    db = _FakeDB(cls)

    _patch_repos(monkeypatch, summary_raw=[])

    data = await analytics_service.get_project_progress_summary(db, teacher_id, class_id=cls.id)

    assert data.projects == []


@pytest.mark.asyncio
async def test_project_progress_summary_empty_class(monkeypatch):
    """班级不存在/不属于该教师时返回空 projects。"""
    teacher_id = uuid4()
    db = _FakeDB(None)  # get(Class) 返回 None

    _patch_repos(monkeypatch, summary_raw=_fake_summary_raw())

    data = await analytics_service.get_project_progress_summary(db, teacher_id, class_id=uuid4())

    assert data.projects == []


@pytest.mark.asyncio
async def test_project_progress_summary_no_classes(monkeypatch):
    """教师没有任何班级时返回空 projects。"""
    teacher_id = uuid4()
    db = _FakeDB(None)

    _patch_repos(monkeypatch, summary_raw=_fake_summary_raw(), classes=[])

    data = await analytics_service.get_project_progress_summary(db, teacher_id, class_id=None)

    assert data.projects == []

# 统计分析--学情总览 Dashboard 消息级互动统计（P1-5.3）测试
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


def _patch_repos(monkeypatch, *, message_raw, sessions_with_msgs, empty=False):
    """把 get_dashboard 依赖的 repos 函数全部替换为假实现。"""

    async def fake_count_class_students(_db, _class_ids, **kw):
        return 10

    async def fake_count_active_students_in_classes(_db, _class_ids, _target_date):
        return 3

    async def fake_count_class_sessions(_db, _class_ids, **kw):
        return 20

    async def fake_list_anomaly_students(_db, _class_ids, **kw):
        return []

    async def fake_get_daily_trend(_db, _class_ids, **kw):
        return []

    async def fake_get_class_comparison(_db, _classes):
        return []

    async def fake_list_student_activity_ranking(_db, _class_ids, **kw):
        return []

    async def fake_get_message_stats(_db, _class_ids, since):
        return message_raw

    async def fake_count_sessions_in_window(_db, _class_ids, since):
        return sessions_with_msgs

    async def fake_list_key_students(_db, _class_ids, since, inactive_threshold_days=7):
        return [
            {
                "user_id": uuid4(),
                "name": "张三",
                "username": "2023001",
                "class_id": uuid4(),
                "class_name": "大一 一班",
                "level": "high_risk",
                "reason": "窗口内有会话但 AI 从未回复",
                "session_count": 2,
                "assistant_messages": 0,
            }
        ]

    monkeypatch.setattr(repos_module, "count_class_students", fake_count_class_students)
    monkeypatch.setattr(repos_module, "count_active_students_in_classes", fake_count_active_students_in_classes)
    monkeypatch.setattr(repos_module, "count_class_sessions", fake_count_class_sessions)
    monkeypatch.setattr(repos_module, "list_anomaly_students", fake_list_anomaly_students)
    monkeypatch.setattr(repos_module, "get_daily_trend", fake_get_daily_trend)
    monkeypatch.setattr(repos_module, "get_class_comparison", fake_get_class_comparison)
    monkeypatch.setattr(repos_module, "list_student_activity_ranking", fake_list_student_activity_ranking)
    monkeypatch.setattr(repos_module, "get_message_stats", fake_get_message_stats)
    monkeypatch.setattr(repos_module, "count_sessions_in_window", fake_count_sessions_in_window)
    monkeypatch.setattr(repos_module, "list_key_students", fake_list_key_students)


@pytest.mark.asyncio
async def test_dashboard_message_stats_computed(monkeypatch):
    """有消息数据时，avg_turns / knowledge_hit_rate 按口径计算并挂载。"""
    teacher_id = uuid4()
    cls = SimpleNamespace(
        id=uuid4(), grade="大一", classname="一班", deleted_at=None, status="active", teacher_id=teacher_id
    )
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        message_raw={
            "total_messages": 12,
            "student_messages": 5,
            "assistant_messages": 7,
            "knowledge_hit_count": 3,
        },
        sessions_with_msgs=4,
    )

    data = await analytics_service.get_dashboard(db, teacher_id, class_id=cls.id, days=30)

    assert data.message_stats.total_messages == 12
    assert data.message_stats.student_messages == 5
    assert data.message_stats.assistant_messages == 7
    assert data.message_stats.avg_turns == 1.8  # round(7/4, 1)
    assert data.message_stats.knowledge_hit_rate == pytest.approx(3 / 5)
    # 重点学生透传
    assert len(data.key_students) == 1
    assert data.key_students[0].level == "high_risk"
    assert data.key_students[0].assistant_messages == 0


@pytest.mark.asyncio
async def test_dashboard_message_stats_empty(monkeypatch):
    """冷启动/无消息时指标归零，不抛除零错误。"""
    teacher_id = uuid4()
    cls = SimpleNamespace(
        id=uuid4(), grade="大一", classname="一班", deleted_at=None, status="active", teacher_id=teacher_id
    )
    db = _FakeDB(cls)

    _patch_repos(
        monkeypatch,
        message_raw={
            "total_messages": 0,
            "student_messages": 0,
            "assistant_messages": 0,
            "knowledge_hit_count": 0,
        },
        sessions_with_msgs=0,
    )

    data = await analytics_service.get_dashboard(db, teacher_id, class_id=cls.id, days=30)

    assert data.message_stats.total_messages == 0
    assert data.message_stats.avg_turns == 0.0
    assert data.message_stats.knowledge_hit_rate == 0.0


@pytest.mark.asyncio
async def test_dashboard_message_stats_empty_class(monkeypatch):
    """班级不存在/不属于该教师时走空数据兜底，message_stats 全零。"""
    teacher_id = uuid4()
    db = _FakeDB(None)  # get(Class) 返回 None

    _patch_repos(
        monkeypatch,
        message_raw={
            "total_messages": 0,
            "student_messages": 0,
            "assistant_messages": 0,
            "knowledge_hit_count": 0,
        },
        sessions_with_msgs=0,
    )

    data = await analytics_service.get_dashboard(db, teacher_id, class_id=uuid4(), days=30)

    assert data.message_stats.total_messages == 0
    assert data.message_stats.avg_turns == 0.0
    assert data.message_stats.knowledge_hit_rate == 0.0
    assert data.key_students == []

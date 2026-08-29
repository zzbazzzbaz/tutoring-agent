# 统计分析--业务逻辑
# analytics/service.py
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics.schemas import (
    AnomalyStudent,
    ClassComparison,
    DashboardOverview,
    DashboardResponse,
    LearningTrendPoint,
    StudentAnalysisResponse,
    StudentClassInfo,
    StudentDailyActivity,
    StudentOverview,
)
from tutoring.db import repos
from tutoring.db.models import Class
from tutoring.core.errors import AppError


async def get_dashboard(
    db: AsyncSession,
    teacher_id: UUID,
    class_id: UUID | None = None,
    days: int = 30,
) -> DashboardResponse:
    """
    获取教师 Dashboard 数据。
    如果指定 class_id 则只返回该班级数据，否则返回该教师所有班级聚合。
    """
    # 1. 获取教师的班级列表
    if class_id:
        single = await db.get(Class, class_id)
        if not single or single.teacher_id != teacher_id or single.deleted_at is not None:
            return _empty_dashboard(days=days)
        classes = [single]
    else:
        classes = await repos.list_classes_by_teacher(db, teacher_id)

    if not classes:
        return _empty_dashboard(days=days)

    class_ids = [c.id for c in classes]
    today = datetime.now(UTC).date()
    seven_days_ago = today - timedelta(days=6)

    # 2. 概览指标
    total_students = await repos.count_class_students(db, class_ids)
    active_today = await repos.count_active_students_in_classes(db, class_ids, today)
    total_sessions = await repos.count_class_sessions(db, class_ids)
    weekly_total = await repos.count_class_sessions(db, class_ids, since=seven_days_ago)
    weekly_avg = round(weekly_total / 7.0, 1)

    # 3. 异常学生列表
    anomalies_raw = await repos.list_anomaly_students(db, class_ids, inactive_threshold_days=7)
    anomalies = [AnomalyStudent(**a) for a in anomalies_raw]

    # 4. 学习趋势(最近N天)
    trend_raw = await repos.get_daily_trend(db, class_ids, days=days)
    trend = [LearningTrendPoint(**t) for t in trend_raw]

    # 5. 班级对比
    comparison_raw = await repos.get_class_comparison(db, classes)
    class_comparison = [ClassComparison(**c) for c in comparison_raw]

    return DashboardResponse(
        overview=DashboardOverview(
            total_students=total_students,
            active_today=active_today,
            total_sessions=total_sessions,
            weekly_avg_sessions=weekly_avg,
            pending_alert_count=len(anomalies),
        ),
        anomalies=anomalies,
        trend=trend,
        class_comparison=class_comparison,
    )


def _empty_dashboard(days: int = 30) -> DashboardResponse:
    """空数据兜底"""
    today = datetime.now(UTC).date()
    return DashboardResponse(
        overview=DashboardOverview(
            total_students=0,
            active_today=0,
            total_sessions=0,
            weekly_avg_sessions=0.0,
            pending_alert_count=0,
        ),
        anomalies=[],
        trend=[
            LearningTrendPoint(
                date=(today - timedelta(days=i)).strftime("%Y-%m-%d"),
                session_count=0,
                active_student_count=0,
            )
            for i in range(days - 1, -1, -1)
        ],
        class_comparison=[],
    )

# === 学生分析 ===

async def get_student_analysis(
    db: AsyncSession,
    teacher_id: UUID,
    user_id: UUID,
) -> StudentAnalysisResponse:
    """
    获取学生分析数据。
    需要验证教师权限（教师只能查看自己班级下的学生）。
    """
    # 1. 获取教师的所有班级
    teacher_classes = await repos.list_classes_by_teacher(db, teacher_id)
    if not teacher_classes:
        raise AppError(404, "NO_CLASS", "教师没有班级")

    class_ids = [c.id for c in teacher_classes]

    # 2. 验证学生是否在教师的班级中
    is_member = False
    for class_id in class_ids:
        if await repos.check_class_member(db, class_id, user_id):
            is_member = True
            break

    if not is_member:
        raise AppError(403, "NOT_CLASS_STUDENT", "该学生不在您的班级中")

    # 3. 获取学生基本信息
    user = await repos.get_user_by_id(db, user_id)
    if not user or user.role != "student":
        raise AppError(404, "STUDENT_NOT_FOUND", "学生不存在")

    # 4. 获取学生学习数据
    learning_data = await repos.get_student_learning_data(db, user_id, class_ids)

    # 5. 获取学生所属班级
    student_classes_raw = await repos.get_student_classes(db, user_id)
    student_classes = [StudentClassInfo(**c) for c in student_classes_raw]

    # 6. 计算未活跃天数
    last_active = learning_data["last_active_at"]
    if last_active is None:
        inactive_days = 999
    else:
        inactive_days = (datetime.now(UTC) - last_active).days

    # 7. 获取每日活动趋势
    daily_activity_raw = await repos.get_student_daily_activity(db, user_id, days=30)
    daily_activity = [StudentDailyActivity(**a) for a in daily_activity_raw]

    return StudentAnalysisResponse(
        overview=StudentOverview(
            user_id=user.id,
            name=user.name,
            username=user.username,
            total_sessions=learning_data["total_sessions"],
            active_days=learning_data["active_days"],
            last_active_at=last_active,
            inactive_days=inactive_days,
            classes=student_classes,
        ),
        daily_activity=daily_activity,
    )
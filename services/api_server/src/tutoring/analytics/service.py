# 统计分析--业务逻辑
# analytics/service.py
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics.schemas import (
    AnomalyStudent,
    ClassComparison,
    ClassEvaluationDimension,
    ClassEvaluationItem,
    ClassEvaluationResponse,
    DashboardOverview,
    DashboardResponse,
    EvaluationMetric,
    KeyStudent,
    LearningTrendPoint,
    MessageStats,
    ProjectProgressResponse,
    ProjectProgressSummary,
    StudentAnalysisResponse,
    StudentClassInfo,
    StudentDailyActivity,
    StudentOverview,
    StudentRanking,
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
        if not single or single.teacher_id != teacher_id or single.deleted_at is not None or single.status != "active":
            return _empty_dashboard(days=days)
        classes = [single]
    else:
        classes = await repos.list_classes_by_teacher(db, teacher_id)

    if not classes:
        return _empty_dashboard(days=days)

    class_ids = [c.id for c in classes]
    today = datetime.now(UTC).date()

    # 2. 概览指标
    total_students = await repos.count_class_students(db, class_ids)
    active_today = await repos.count_active_students_in_classes(db, class_ids, today)
    total_sessions = await repos.count_class_sessions(db, class_ids)

    # 3. 异常学生列表
    anomalies_raw = await repos.list_anomaly_students(db, class_ids, inactive_threshold_days=7)
    anomalies = [AnomalyStudent(**a) for a in anomalies_raw]

    # 4. 学习趋势(最近N天)
    trend_raw = await repos.get_daily_trend(db, class_ids, days=days)
    trend = [LearningTrendPoint(**t) for t in trend_raw]

    # 5. 班级对比
    comparison_raw = await repos.get_class_comparison(db, classes)
    class_comparison = [ClassComparison(**c) for c in comparison_raw]

    # 6. 对话模式分布(自由模式 vs 项目模式)
    free_count = await repos.count_class_sessions(db, class_ids, mode="free")
    project_count = await repos.count_class_sessions(db, class_ids, mode="project")
    mode_distribution = [
        {"mode": "project", "count": project_count},
        {"mode": "free", "count": free_count},
    ]

    # 7. 学生活跃度排行(按累计对话数降序)
    ranking_raw = await repos.list_student_activity_ranking(db, class_ids, limit=50)
    student_ranking = [StudentRanking(**r) for r in ranking_raw]

    # 8. 消息级互动明细 + 知识命中率（数据源：message 表，窗口与趋势一致为 days 个自然日）
    window_start = today - timedelta(days=days - 1)
    msg_raw = await repos.get_message_stats(db, class_ids, since=window_start)
    msg_sessions = await repos.count_sessions_in_window(db, class_ids, since=window_start)
    assistant_count = msg_raw["assistant_messages"]
    student_count = msg_raw["student_messages"]
    avg_turns = round(assistant_count / msg_sessions, 1) if msg_sessions > 0 else 0.0       # 平均轮次 = AI回复 ÷ 有消息的会话数
    hit_rate = (
        round(msg_raw["knowledge_hit_count"] / student_count, 4) if student_count > 0 else 0.0  # 命中率 = 命中知识库 ÷ 学生提问
    )
    message_stats = MessageStats(
        total_messages=msg_raw["total_messages"],
        student_messages=student_count,
        assistant_messages=assistant_count,
        avg_turns=avg_turns,
        knowledge_hit_rate=hit_rate,
    )

    # 9. 重点学生（高风险/高优先级，窗口与互动明细一致）
    key_students_raw = await repos.list_key_students(db, class_ids, since=window_start)
    key_students = [KeyStudent(**k) for k in key_students_raw]

    return DashboardResponse(
        overview=DashboardOverview(
            total_students=total_students,
            active_today=active_today,
            total_sessions=total_sessions,
            pending_alert_count=len(anomalies),
        ),
        anomalies=anomalies,
        trend=trend,
        class_comparison=class_comparison,
        mode_distribution=mode_distribution,
        student_ranking=student_ranking,
        message_stats=message_stats,
        key_students=key_students,
    )


def _empty_dashboard(days: int = 30) -> DashboardResponse:
    """空数据兜底"""
    today = datetime.now(UTC).date()
    return DashboardResponse(
        overview=DashboardOverview(
            total_students=0,
            active_today=0,
            total_sessions=0,
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
        mode_distribution=[],
        student_ranking=[],
        message_stats=MessageStats(
            total_messages=0,
            student_messages=0,
            assistant_messages=0,
            avg_turns=0.0,
            knowledge_hit_rate=0.0,
        ),
        key_students=[],
    )

# === 学生分析 ===

async def get_student_analysis(
    db: AsyncSession,
    teacher_id: UUID,
    user_id: UUID,
    days: int = 30,
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
    if not user or user.role != "student" or user.deleted_at is not None:
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

    # 7 最近7天对话数（今天+前6天）
    seven_days_ago = datetime.now(UTC).date() - timedelta(days=6)
    weekly_sessions = await repos.count_student_sessions_since(db, user_id, seven_days_ago)

    # 8. 获取每日活动趋势
    daily_activity_raw = await repos.get_student_daily_activity(db, user_id, days=days)
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
            weekly_sessions=weekly_sessions,
            classes=student_classes,
        ),
        daily_activity=daily_activity,
    )


# === 项目维度进度聚合===

async def get_project_progress_summary(
    db: AsyncSession,
    teacher_id: UUID,
    class_id: UUID | None = None,
) -> ProjectProgressResponse:
    """
    项目维度进度聚合（阶段分布 / 产出物完成）。

    口径：学生 × 项目合并会话进度（跨会话累积的当前状态），**不限时间窗口**，
    不随报告天数切换变化。班级解析与 get_dashboard 一致：
    指定 class_id 时校验归属，否则聚合该教师全部班级。
    """
    if class_id:
        single = await db.get(Class, class_id)
        if not single or single.teacher_id != teacher_id or single.deleted_at is not None or single.status != "active":
            return ProjectProgressResponse(projects=[])
        classes = [single]
    else:
        classes = await repos.list_classes_by_teacher(db, teacher_id)

    if not classes:
        return ProjectProgressResponse(projects=[])

    class_ids = [c.id for c in classes]
    raw = await repos.list_project_progress_summary(db, class_ids=class_ids)
    return ProjectProgressResponse(projects=[ProjectProgressSummary(**p) for p in raw])


# === 班级评价===

# 参与度口径：
# 参与度 = 活跃率×40% + 会话强度×30% + 互动深度×30%（0-100）
# - 活跃率   = 窗口内有过会话的学生数 ÷ 班级学生总数 × 100（天然 0-100）
# - 会话强度 = 窗口内会话数 ÷ 学生总数，人均 5 次为满分（封顶 100）
# - 互动深度 = 窗口内学生发起消息数 ÷ 学生总数，人均 30 条为满分（封顶 100）
# 等级：≥80 高 / 60-79 中 / <60 低
_PARTICIPATION_SESSION_FULL = 5.0   # 人均 5 会话 = 会话强度满分
_PARTICIPATION_MSG_FULL = 30.0      # 人均 30 条学生消息 = 互动深度满分
_PARTICIPATION_W = {"active_rate": 0.4, "session": 0.3, "message": 0.3}


def _build_participation_dimension(stats: dict) -> ClassEvaluationDimension:
    """由参与度统计组装「参与度」维度（含证据指标）。"""
    total = stats["total_students"]
    if total <= 0:
        score = 0
    else:
        active_rate = stats["active_students"] / total
        session_score = min(stats["sessions"] / total / _PARTICIPATION_SESSION_FULL, 1.0)
        message_score = min(
            stats["student_messages"] / total / _PARTICIPATION_MSG_FULL, 1.0
        )
        score = round(
            (
                active_rate * _PARTICIPATION_W["active_rate"]
                + session_score * _PARTICIPATION_W["session"]
                + message_score * _PARTICIPATION_W["message"]
            )
            * 100
        )
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    metrics = [
        EvaluationMetric(label="活跃天数", value=str(stats["active_days"])),
        EvaluationMetric(label="会话数", value=str(stats["sessions"])),
        EvaluationMetric(label="学生发起消息", value=str(stats["student_messages"])),
        EvaluationMetric(
            label="活跃学生",
            value=f'{stats["active_students"]}/{total}',
        ),
    ]
    return ClassEvaluationDimension(
        dimension_id="participation",
        name="参与度",
        score=score,
        level=level,
        metrics=metrics,
    )


async def get_class_evaluation(
    db: AsyncSession,
    teacher_id: UUID,
    class_id: UUID | None = None,
    days: int = 30,
) -> ClassEvaluationResponse:
    """班级评价（六维：「参与度」+「思考质量」+「知识运用」+「产出物完成」+「阶段覆盖」+「学科」维度。

    班级解析：
    - 指定 class_id：校验归属后仅返回该班级（1 项），前端渲染六维卡片
    - class_id=None（全部班级）：**逐班级独立计算**各维度并全部返回（N 项），
      前端渲染班级×维度横向对比表；不做跨班混算（混算会抹平班级差异）
    - 班级不存在/不属于该教师/教师无班级：返回空 classes

    窗口：参与度/思考质量/知识运用/学科知识点覆盖按报告 7/30 天窗口；产出物完成/
    阶段覆盖/学科按项目维度聚合口径（跨会话累积、不限时间窗口，与报告
    「三、阶段分布与产出物完成」板块一致，产出物/阶段进度是跨会话累积的当前状态，
    不应随窗口切换而消失）。
    """
    if class_id:
        single = await db.get(Class, class_id)
        if not single or single.teacher_id != teacher_id or single.deleted_at is not None or single.status != "active":
            return ClassEvaluationResponse(days=days, classes=[])
        classes = [single]
    else:
        classes = await repos.list_classes_by_teacher(db, teacher_id)
        if not classes:
            return ClassEvaluationResponse(days=days, classes=[])

    today = datetime.now(UTC).date()
    since = today - timedelta(days=days - 1)

    items: list[ClassEvaluationItem] = []
    for cls in classes:
        class_ids = [cls.id]
        participation_stats = await repos.get_class_participation_stats(
            db, class_ids=class_ids, since=since
        )
        # 消息级统计同时喂给「思考质量」与「知识运用」两个维度（同一查询，不重复取数）
        msg_stats = await repos.get_class_thinking_stats(db, class_ids=class_ids, since=since)
        # 产出物完成/阶段覆盖：复用项目维度进度聚合（跨会话累积、不限时间窗口，与报告「三」板块口径一致）
        project_progress_raw = await repos.list_project_progress_summary(
            db, class_ids=class_ids
        )
        # 学科知识点覆盖：消息级（窗口内项目模式会话 knowledge_doc_ids）
        subject_stats = await repos.get_class_subject_stats(
            db, class_ids=class_ids, since=since
        )
        dimensions = [
            _build_participation_dimension(participation_stats),
            _build_thinking_dimension(msg_stats),
            _build_knowledge_dimension(msg_stats),
            _build_deliverable_dimension(project_progress_raw),
            _build_stage_coverage_dimension(project_progress_raw),
            _build_subject_dimension(subject_stats, project_progress_raw),
        ]
        items.append(
            ClassEvaluationItem(
                class_id=cls.id,
                class_name=f"{cls.grade} {cls.classname}",
                dimensions=dimensions,
            )
        )

    return ClassEvaluationResponse(days=days, classes=items)


# 思考质量口径：
# 思考质量 = 提问深度×30% + 主动追问×25% + 知识命中率×25% + 多轮持续度×20%（0-100）
# - 提问深度   = 含深度词的学生提问 ÷ 学生提问总数 × 100（深度词见 repos._THINKING_DEPTH_PATTERN）
# - 主动追问   = 非会话首条的学生消息 ÷ 学生消息总数 × 100
# - 知识命中率 = 命中知识库的学生提问 ÷ 学生提问总数 × 100（复用互动明细口径）
# - 多轮持续度 = 平均轮次(AI回复÷有消息会话数)，人均 5 轮为满分（封顶 100）
# 等级：≥80 高 / 60-79 中 / <60 低
_THINKING_W = {"depth": 0.30, "follow_up": 0.25, "hit_rate": 0.25, "turns": 0.20}
_THINKING_TURNS_FULL = 5.0


def _build_thinking_dimension(stats: dict) -> ClassEvaluationDimension:
    """由思考质量统计组装「思考质量」维度（含证据指标）。"""
    student = stats["student_messages"]
    assistant = stats["assistant_messages"]
    sessions = stats["sessions_with_messages"]
    if student > 0:
        depth_score = stats["deep_questions"] / student
        follow_score = stats["follow_up_messages"] / student
        hit_score = stats["knowledge_hit_count"] / student
        turns_score = (
            min(assistant / sessions / _THINKING_TURNS_FULL, 1.0) if sessions > 0 else 0.0
        )
    else:
        # 无学生提问：思考质量无从评估，整体归 0（含轮次，避免半截数据）
        depth_score = follow_score = hit_score = turns_score = 0.0

    score = round(
        (
            depth_score * _THINKING_W["depth"]
            + follow_score * _THINKING_W["follow_up"]
            + hit_score * _THINKING_W["hit_rate"]
            + turns_score * _THINKING_W["turns"]
        )
        * 100
    )
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    hit_rate_pct = round(stats["knowledge_hit_count"] / student * 100) if student > 0 else 0
    avg_turns = round(assistant / sessions, 1) if sessions > 0 else 0.0
    metrics = [
        EvaluationMetric(label="学生提问", value=str(student)),
        EvaluationMetric(label="深度提问", value=str(stats["deep_questions"])),
        EvaluationMetric(label="主动追问", value=str(stats["follow_up_messages"])),
        EvaluationMetric(label="知识命中率", value=f"{hit_rate_pct}%"),
        EvaluationMetric(label="平均轮次", value=str(avg_turns)),
    ]
    return ClassEvaluationDimension(
        dimension_id="thinking",
        name="思考质量",
        score=score,
        level=level,
        metrics=metrics,
    )


# 知识运用口径：
# 知识运用 = 命中知识库的学生提问 ÷ 学生提问总数 × 100（0-100，天然无需归一/无权重）
# 无学生提问时归 0；等级：≥80 高 / 60-79 中 / <60 低
def _build_knowledge_dimension(stats: dict) -> ClassEvaluationDimension:
    """由消息级统计组装「知识运用」维度（即知识命中率，含证据指标）。"""
    student = stats["student_messages"]
    hit = stats["knowledge_hit_count"]
    score = round(hit / student * 100) if student > 0 else 0
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    metrics = [
        EvaluationMetric(label="学生提问", value=str(student)),
        EvaluationMetric(label="命中提问", value=str(hit)),
        EvaluationMetric(label="知识命中率", value=f"{score}%"),
    ]
    return ClassEvaluationDimension(
        dimension_id="knowledge",
        name="知识运用",
        score=score,
        level=level,
        metrics=metrics,
    )


# 产出物完成口径：
# 产出物完成 = 提交率×50% + 达标率×50%（0-100）
# - 提交率 = 已提交产出物条目 ÷ 可提交条目（参与学生 × 有产出物阶段数）
# - 达标率 = 已达标条目 ÷ 已提交条目（无提交时按 0）
# - 数据源：list_project_progress_summary（阶段①统计，跨会话累积、不限时间窗口）
# - 无参与项目/无可提交条目时归 0；等级：≥80 高 / 60-79 中 / <60 低
def _build_deliverable_dimension(raw_projects: list[dict]) -> ClassEvaluationDimension:
    """由项目维度进度聚合结果组装「产出物完成」维度（含证据指标）。

    raw_projects 即 list_project_progress_summary 的返回：仅统计参与学生>0 的项目，
    未启动项目（student_count=0）不进入可提交条目，也不计入参与项目数。
    """
    expected = 0
    submitted = 0
    done = 0
    active_projects = 0
    for proj in raw_projects:
        if proj["student_count"] <= 0:
            continue
        active_projects += 1
        stages_with_deliverable = sum(1 for st in proj["stages"] if st["has_deliverable"])
        expected += proj["student_count"] * stages_with_deliverable
        submitted += sum(st["deliverable_submitted_count"] for st in proj["stages"])
        done += sum(st["deliverable_done_count"] for st in proj["stages"])

    submit_rate = submitted / expected if expected > 0 else 0.0
    pass_rate = done / submitted if submitted > 0 else 0.0
    score = round((submit_rate * 0.5 + pass_rate * 0.5) * 100)
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    metrics = [
        EvaluationMetric(label="参与项目", value=str(active_projects)),
        EvaluationMetric(label="可提交条目", value=str(expected)),
        EvaluationMetric(label="已提交条目", value=str(submitted)),
        EvaluationMetric(label="已达标条目", value=str(done)),
        EvaluationMetric(label="提交率", value=f"{round(submit_rate * 100)}%"),
        EvaluationMetric(label="达标率", value=f"{round(pass_rate * 100)}%"),
    ]
    return ClassEvaluationDimension(
        dimension_id="deliverable",
        name="产出物完成",
        score=score,
        level=level,
        metrics=metrics,
    )


# 阶段覆盖口径：
# 阶段覆盖 = 阶段完成率×70% + 阶段覆盖率×30%（0-100）
# - 应覆盖条目（分母） = Σ(参与学生 × 项目阶段总数)，仅统计参与学生>0 的项目
# - 阶段完成率 = 已完成条目（Σ各阶段 completed_count）÷ 应覆盖条目
# - 阶段覆盖率 = 已推进条目（Σ各阶段 started_count，即 in_progress+completed）÷ 应覆盖条目
#   —— 衡量学生触及阶段定义的广度
# - 数据源：list_project_progress_summary（阶段统计，跨会话累积、不限时间窗口）
# - 无参与项目时归 0；等级：≥80 高 / 60-79 中 / <60 低
_STAGE_COVERAGE_W = {"completed": 0.70, "started": 0.30}


def _build_stage_coverage_dimension(raw_projects: list[dict]) -> ClassEvaluationDimension:
    """由项目维度进度聚合结果组装「阶段覆盖」维度（含证据指标）。

    raw_projects 即 list_project_progress_summary 的返回：仅统计参与学生>0 的项目，
    未启动项目（student_count=0）不进入应覆盖条目，也不计入参与项目数。
    """
    expected = 0
    completed = 0
    started = 0
    active_projects = 0
    active_students = 0
    for proj in raw_projects:
        if proj["student_count"] <= 0:
            continue
        active_projects += 1
        active_students += proj["student_count"]
        expected += proj["student_count"] * proj["stage_count"]
        completed += sum(st["completed_count"] for st in proj["stages"])
        started += sum(st["started_count"] for st in proj["stages"])

    complete_rate = completed / expected if expected > 0 else 0.0
    coverage_rate = started / expected if expected > 0 else 0.0
    score = round(
        (
            complete_rate * _STAGE_COVERAGE_W["completed"]
            + coverage_rate * _STAGE_COVERAGE_W["started"]
        )
        * 100
    )
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    metrics = [
        EvaluationMetric(label="参与项目", value=str(active_projects)),
        EvaluationMetric(label="参与学生", value=str(active_students)),
        EvaluationMetric(label="应覆盖条目", value=str(expected)),
        EvaluationMetric(label="已开始条目", value=str(started)),
        EvaluationMetric(label="已完成条目", value=str(completed)),
        EvaluationMetric(label="阶段完成率", value=f"{round(complete_rate * 100)}%"),
        EvaluationMetric(label="阶段覆盖率", value=f"{round(coverage_rate * 100)}%"),
    ]
    return ClassEvaluationDimension(
        dimension_id="stage_coverage",
        name="阶段覆盖",
        score=score,
        level=level,
        metrics=metrics,
    )


# 学科维度口径：
# 学科维度 = 知识点覆盖×40% + 案例分析×30% + 情境应用×30%（0-100）
# 知识点覆盖 = 学生人均命中去重文档数 ÷ 全班命中去重文档总数 × 100
#   - 范围：班级内项目模式会话、报告 7/30 天窗口、仅 student 消息（knowledge_doc_ids）
#   - 人均 = Σ(每学生命中去重文档数) ÷ 参与项目学生数；全班 = 命中去重文档总数
#   - 数学上人均 ≤ 全班（每学生去重数 ≤ 全班去重），比率恒 ≤ 100；无命中归 0
#  案例分析质量 = 案例类产出物已达标条目 ÷ 已提交条目 × 100（无提交归 0）
#   - 案例类 = 产出物标题含"记录/案例/观察/分析"（任一）
#  情境应用 = 方案类产出物已达标条目 ÷ 已提交条目 × 100（无提交归 0）
#   - 方案类 = 产出物标题含"方案/设计/计划/策略"（任一）
# 按项目维度聚合（跨会话累积、不限时间窗口，与产出物完成/阶段覆盖一致）；
# 标题分类互斥（先案例后方案，都不含不计入）；未启动项目（student_count=0）排除。
# 等级：≥80 高 / 60-79 中 / <60 低
_SUBJECT_W = {"knowledge": 0.40, "case": 0.30, "plan": 0.30}
_SUBJECT_CASE_PATTERN = r"记录|案例|观察|分析"
_SUBJECT_PLAN_PATTERN = r"方案|设计|计划|策略"


def _build_subject_dimension(
    subject_stats: dict, raw_projects: list[dict]
) -> ClassEvaluationDimension:
    """组装「学科」维度（知识点覆盖 + 案例分析 + 情境应用，含证据指标）。

    subject_stats 即 repos.get_class_subject_stats 的返回（知识点覆盖数据源）；
    raw_projects 即 list_project_progress_summary 的返回（案例分析/情境应用数据源）。
    """
    # 知识点覆盖
    doc_counts = list(subject_stats["student_doc_counts"].values())
    total_individual = sum(doc_counts)
    project_students = subject_stats["project_students"]
    class_doc_count = subject_stats["class_doc_count"]
    per_student = total_individual / project_students if project_students > 0 else 0.0
    coverage_ratio = per_student / class_doc_count if class_doc_count > 0 else 0.0

    # 案例分析质量 / 情境应用（从项目维度进度聚合按标题分类，互斥：案例优先）
    case_submitted = case_done = plan_submitted = plan_done = 0
    for proj in raw_projects:
        if proj["student_count"] <= 0:
            continue
        for st in proj["stages"]:
            title = st.get("deliverable_title") or ""
            submitted = st["deliverable_submitted_count"]
            done = st["deliverable_done_count"]
            if re.search(_SUBJECT_CASE_PATTERN, title):
                case_submitted += submitted
                case_done += done
            elif re.search(_SUBJECT_PLAN_PATTERN, title):
                plan_submitted += submitted
                plan_done += done

    case_rate = case_done / case_submitted if case_submitted > 0 else 0.0
    plan_rate = plan_done / plan_submitted if plan_submitted > 0 else 0.0
    score = round(
        (
            coverage_ratio * _SUBJECT_W["knowledge"]
            + case_rate * _SUBJECT_W["case"]
            + plan_rate * _SUBJECT_W["plan"]
        )
        * 100
    )
    level = "高" if score >= 80 else ("中" if score >= 60 else "低")
    metrics = [
        EvaluationMetric(label="命中涉及学生", value=str(len(doc_counts))),
        EvaluationMetric(label="命中文档(全班)", value=str(class_doc_count)),
        EvaluationMetric(
            label="知识点覆盖", value=f"{round(coverage_ratio * 100)}%"
        ),
        EvaluationMetric(label="案例类提交", value=str(case_submitted)),
        EvaluationMetric(label="案例类达标", value=str(case_done)),
        EvaluationMetric(label="案例分析达标率", value=f"{round(case_rate * 100)}%"),
        EvaluationMetric(label="方案类提交", value=str(plan_submitted)),
        EvaluationMetric(label="方案类达标", value=str(plan_done)),
        EvaluationMetric(label="情境应用达标率", value=f"{round(plan_rate * 100)}%"),
    ]
    return ClassEvaluationDimension(
        dimension_id="subject",
        name="学科",
        score=score,
        level=level,
        metrics=metrics,
    )
# 统计分析--路由
# analytics/router.py
from datetime import datetime
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics import export as analytics_export
from tutoring.analytics import scoring_service
from tutoring.analytics import service as analytics_service
from tutoring.analytics import summary as analytics_summary
from tutoring.analytics.schemas import (
    ClassEvaluationResponse,
    DashboardResponse,
    DashboardSummaryResponse,
    ProjectProgressResponse,
    ScoringGenerateRequest,
    ScoringPromptResponse,
    ScoringPromptUpdate,
    ScoringResultResponse,
    StudentAnalysisResponse,
    StudentScoreItem,
)
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Class

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可访问统计分析")


# 学情总览路由
@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    class_id: UUID | None = Query(None, description="班级ID,不传则返回该教师所有班级聚合"),
    days: int = Query(30, ge=7, le=30, description="趋势图天数(7或30)"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    _require_teacher(user)
    data = await analytics_service.get_dashboard(db, user.id, class_id, days=days)
    return data

# 研究摘要（LLM 生成，独立接口不拖慢学情总览；未配置/异常时 503，前端回退规则摘要）
@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    class_id: UUID | None = Query(None, description="班级ID,不传则返回该教师所有班级聚合"),
    days: int = Query(30, ge=7, le=30, description="统计天数(7或30)"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    _require_teacher(user)
    dashboard = await analytics_service.get_dashboard(db, user.id, class_id, days=days)
    try:
        summary_text = await analytics_summary.generate_summary(dashboard)
    except analytics_summary.SummaryUnavailable:
        raise AppError(
            503,
            "SUMMARY_UNAVAILABLE",
            "AI 摘要暂不可用：DASHSCOPE_API_KEY 未配置或 LLM 服务异常",
        )
    return DashboardSummaryResponse(summary=summary_text, source="llm")

# 学生分析路由
@router.get("/students/{user_id}", response_model=StudentAnalysisResponse)
async def get_student_analysis(
    user_id: UUID,
    days: int = Query(30, ge=7, le=30, description="活动趋势天数"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentAnalysisResponse:
    """获取学生分析数据"""
    _require_teacher(user)
    return await analytics_service.get_student_analysis(db, user.id, user_id, days=days)

# 项目维度进度聚合（阶段分布/产出物完成）——进度为跨会话累积的当前状态，不限时间窗口
@router.get("/project-progress", response_model=ProjectProgressResponse)
async def get_project_progress(
    class_id: UUID | None = Query(None, description="班级ID,不传则返回该教师所有班级聚合"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectProgressResponse:
    """项目维度进度聚合（阶段分布/产出物完成）。"""
    _require_teacher(user)
    return await analytics_service.get_project_progress_summary(db, user.id, class_id)


# 班级评价
@router.get("/class-evaluation", response_model=ClassEvaluationResponse)
async def get_class_evaluation(
    class_id: UUID | None = Query(None, description="班级ID,不传则返回该教师所有班级聚合"),
    days: int = Query(30, ge=7, le=30, description="统计窗口天数(7或30)"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassEvaluationResponse:
    """班级评价"""
    _require_teacher(user)
    return await analytics_service.get_class_evaluation(db, user.id, class_id, days=days)


# 导出使用统计报告（Word 文档下载）
@router.get("/export-report")
async def export_report(
    class_id: UUID | None = Query(None, description="班级ID,不传则导出该教师所有班级聚合报告"),
    days: int = Query(30, ge=7, le=30, description="统计窗口天数(7或30)"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """导出使用统计报告（Word .docx 下载）。"""
    _require_teacher(user)
    dashboard = await analytics_service.get_dashboard(db, user.id, class_id, days=days)
    progress = await analytics_service.get_project_progress_summary(db, user.id, class_id)
    evaluation = await analytics_service.get_class_evaluation(db, user.id, class_id, days=days)

    if class_id:
        cls = await db.get(Class, class_id)
        scope_label = f"{cls.grade} {cls.classname}" if cls else "未指定班级"
    else:
        classes = await repos.list_classes_by_teacher(db, user.id)
        scope_label = f"全部班级（共 {len(classes)} 个）"

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    buf = analytics_export.build_report_docx(
        dashboard=dashboard,
        progress=progress,
        evaluation=evaluation,
        scope_label=scope_label,
        days=days,
        generated_at=now,
    )
    filename = f"使用统计报告_{now.strftime('%Y%m%d_%H%M')}.docx"
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# === 平时分（AI 评分） ===


def _get_own_class(cls: Class | None, teacher_id: UUID) -> Class:
    """校验班级存在且属于该教师，否则 404。"""
    if (
        not cls
        or cls.teacher_id != teacher_id
        or cls.deleted_at is not None
        or cls.status != "active"
    ):
        raise AppError(404, "CLASS_NOT_FOUND", "班级不存在或不属于当前教师")
    return cls


def _rows_to_items(rows: list[dict]) -> list[StudentScoreItem]:
    """repos.list_class_student_scores 行 → 响应条目。"""
    return [
        StudentScoreItem(
            student_id=r["student_id"],
            name=r["name"],
            username=r["username"],
            score=r["score"],
            reason=r["reason"],
            metrics=r["metrics"],
        )
        for r in rows
    ]


# 平时分--提示词读写
@router.get("/scoring/prompt", response_model=ScoringPromptResponse)
async def get_scoring_prompt(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoringPromptResponse:
    """读取评分提示词（未自定义时返回系统默认模板）。"""
    _require_teacher(user)
    row = await repos.get_scoring_prompt(db, user.id)
    if row is None:
        return ScoringPromptResponse(
            prompt=scoring_service.DEFAULT_SCORING_PROMPT, is_default=True
        )
    return ScoringPromptResponse(prompt=row.prompt, is_default=False)


@router.patch("/scoring/prompt", response_model=ScoringPromptResponse)
async def update_scoring_prompt(
    body: ScoringPromptUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoringPromptResponse:
    """保存评分提示词。"""
    _require_teacher(user)
    await repos.upsert_scoring_prompt(db, user.id, body.prompt)
    return ScoringPromptResponse(prompt=body.prompt, is_default=False)


# 平时分--生成
@router.post("/scoring/generate", response_model=ScoringResultResponse)
async def generate_scoring(
    body: ScoringGenerateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoringResultResponse:
    """生成班级平时分（AI 评分，同步，约 30-60s）。"""
    _require_teacher(user)
    try:
        return await scoring_service.generate_scores(db, user.id, body.class_id, body.since)
    except scoring_service.ScoringUnavailable as exc:
        raise AppError(503, "SCORING_UNAVAILABLE", f"AI 评分暂不可用：{exc}") from exc


# 平时分--读取最近结果
@router.get("/scoring", response_model=ScoringResultResponse)
async def get_scoring(
    class_id: UUID = Query(..., description="班级ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoringResultResponse:
    """读取该班最近一次平时分结果。"""
    _require_teacher(user)
    cls = _get_own_class(await db.get(Class, class_id), user.id)
    rows = await repos.list_class_student_scores(db, class_id)
    return ScoringResultResponse(
        class_id=class_id,
        class_name=f"{cls.grade} {cls.classname}",
        since=rows[0]["since"] if rows else None,
        generated_at=max(r["generated_at"] for r in rows) if rows else None,
        items=_rows_to_items(rows),
    )


# 平时分--导出 Word
@router.get("/scoring/export")
async def export_scoring(
    class_id: UUID = Query(..., description="班级ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """导出平时分成绩表（Word .docx 下载）。"""
    _require_teacher(user)
    cls = _get_own_class(await db.get(Class, class_id), user.id)
    rows = await repos.list_class_student_scores(db, class_id)
    result = ScoringResultResponse(
        class_id=class_id,
        class_name=f"{cls.grade} {cls.classname}",
        since=rows[0]["since"] if rows else None,
        generated_at=max(r["generated_at"] for r in rows) if rows else None,
        items=_rows_to_items(rows),
    )
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    buf = analytics_export.build_scoring_docx(result=result, generated_at=now)
    filename = f"平时分成绩表_{now.strftime('%Y%m%d_%H%M')}.docx"
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
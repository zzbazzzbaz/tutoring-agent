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
from tutoring.analytics import service as analytics_service
from tutoring.analytics import summary as analytics_summary
from tutoring.analytics.schemas import (
    ClassEvaluationResponse,
    DashboardResponse,
    DashboardSummaryResponse,
    ProjectProgressResponse,
    StudentAnalysisResponse,
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
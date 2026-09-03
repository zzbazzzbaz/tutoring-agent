# 统计分析--路由
# analytics/router.py
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics import service as analytics_service
from tutoring.analytics import summary as analytics_summary
from tutoring.analytics.schemas import (
    DashboardResponse,
    DashboardSummaryResponse,
    ProjectProgressResponse,
    StudentAnalysisResponse,
)
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError

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
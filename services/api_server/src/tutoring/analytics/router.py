# 统计分析--路由
# analytics/router.py
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics import service as analytics_service
from tutoring.analytics.schemas import DashboardResponse, StudentAnalysisResponse
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
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    _require_teacher(user)
    data = await analytics_service.get_dashboard(db, user.id, class_id)
    return data

# 学生分析路由
@router.get("/students/{user_id}", response_model=StudentAnalysisResponse)
async def get_student_analysis(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentAnalysisResponse:
    """获取学生分析数据"""
    _require_teacher(user)
    return await analytics_service.get_student_analysis(db, user.id, user_id)
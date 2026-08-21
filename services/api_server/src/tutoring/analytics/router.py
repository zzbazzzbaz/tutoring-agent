# 统计分析--路由
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics import service as analytics_service
from tutoring.analytics.schemas import DashboardResponse
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可访问统计分析")


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    class_id: UUID | None = Query(None, description="班级ID,不传则返回该教师所有班级聚合"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    _require_teacher(user)
    data = await analytics_service.get_dashboard(db, user.id, class_id)
    return data

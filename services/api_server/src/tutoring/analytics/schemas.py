# 统计分析--响应模型
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# 学情总览--响应模型
class DashboardOverview(BaseModel):
    """学情总览概览指标"""
    total_students: int = Field(description="班级总学生数")
    active_today: int = Field(description="今日活跃学生数")
    total_sessions: int = Field(description="累计对话总数")
    weekly_avg_sessions: float = Field(description="周均对话次数(所有学生)")
    pending_alert_count: int = Field(description="待关注学生数")

class AnomalyStudent(BaseModel):
    """异常学生条目"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    name: str
    username: str
    last_active_at: datetime | None = None
    inactive_days: int = Field(description="未活跃天数")
    alert_type: Literal["inactive"] = Field(description="预警类型")
    class_id: UUID
    class_name: str

class LearningTrendPoint(BaseModel):
    """学习趋势数据点"""
    date: str = Field(description="日期 YYYY-MM-DD")
    session_count: int = Field(description="当日对话数")
    active_student_count: int = Field(description="当日活跃学生数")

class ClassComparison(BaseModel):
    """班级对比数据"""
    class_id: UUID
    class_name: str
    total_students: int
    active_today: int
    active_rate: float = Field(description="今日活跃率 0-1")

class DashboardResponse(BaseModel):
    """Dashboard 完整响应"""
    overview: DashboardOverview = Field(description="概览指标")
    anomalies: list[AnomalyStudent] = Field(description="异常学生列表")
    trend: list[LearningTrendPoint] = Field(description="学习趋势数据")
    class_comparison: list[ClassComparison] = Field(description="班级对比数据")

# ===========================================================================
# 学生分析--响应模型

class StudentClassInfo(BaseModel):
    """学生所属班级信息"""
    class_id: UUID = Field(description="班级ID")
    class_name: str = Field(description="班级名称")
    joined_at: datetime = Field(description="加入时间")

class StudentOverview(BaseModel):
    """学生基本学习数据"""
    user_id: UUID = Field(description="学生ID")
    name: str = Field(description="学生姓名")
    username: str = Field(description="学号")
    total_sessions: int = Field(description="累计对话数")
    active_days: int = Field(description="活跃天数")
    last_active_at: datetime | None = Field(default=None, description="最后活跃时间")
    inactive_days: int = Field(description="未活跃天数")
    classes: list[StudentClassInfo] = Field(description="所属班级列表")

class StudentDailyActivity(BaseModel):
    """学生每日活动数据点"""
    date: str = Field(description="日期 YYYY-MM-DD")
    session_count: int = Field(description="当日对话数")


class StudentAnalysisResponse(BaseModel):
    """学生分析完整响应"""
    overview: StudentOverview = Field(description="学生概览")
    daily_activity: list[StudentDailyActivity] = Field(description="每日活动趋势")
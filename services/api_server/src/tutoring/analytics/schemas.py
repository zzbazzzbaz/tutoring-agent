# 统计分析--响应模型
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# 学情总览--响应模型
class DashboardOverview(BaseModel):
    """学情总览概览指标"""
    total_students: int = Field(description="班级总学生数")
    active_today: int = Field(description="今日活跃学生数")
    total_sessions: int = Field(description="累计对话总数")
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

class ModeCount(BaseModel):
    """对话模式计数"""
    mode: Literal["free", "project"] = Field(description="模式: free自由/project项目")
    count: int = Field(description="对话数")

class StudentRanking(BaseModel):
    """学生活跃度排行条目"""
    user_id: UUID
    name: str
    username: str
    total_sessions: int = Field(description="累计对话数")
    active_days: int = Field(description="活跃天数")
    last_active_at: datetime | None = Field(default=None, description="最后活跃时间")

class MessageStats(BaseModel):
    """消息级互动统计（互动明细 / 知识命中率）"""
    total_messages: int = Field(description="总互动(学生发起+AI回复)")
    student_messages: int = Field(description="学生发起数")
    assistant_messages: int = Field(description="AI回复数(轮次)")
    avg_turns: float = Field(description="平均轮次(AI回复/窗口内有消息的会话数)")
    knowledge_hit_rate: float = Field(description="知识命中率(命中知识的学生提问/学生提问总数) 0-1")

class KeyStudent(BaseModel):
    """重点学生条目（高风险/高优先级）"""
    user_id: UUID
    name: str
    username: str
    class_id: UUID
    class_name: str
    level: Literal["high_risk", "high_priority"] = Field(description="重点等级: high_risk高风险/high_priority高优先级")
    reason: str = Field(description="命中规则说明")
    session_count: int = Field(description="窗口内会话数")
    assistant_messages: int = Field(description="窗口内AI回复数")

class DashboardResponse(BaseModel):
    """Dashboard 完整响应"""
    overview: DashboardOverview = Field(description="概览指标")
    anomalies: list[AnomalyStudent] = Field(description="异常学生列表")
    trend: list[LearningTrendPoint] = Field(description="学习趋势数据")
    class_comparison: list[ClassComparison] = Field(description="班级对比数据")
    mode_distribution: list[ModeCount] = Field(description="对话模式分布")
    student_ranking: list[StudentRanking] = Field(description="学生活跃度排行")
    message_stats: MessageStats = Field(description="消息级互动统计(互动明细)")
    key_students: list[KeyStudent] = Field(description="重点学生(高风险/高优先级)")

class DashboardSummaryResponse(BaseModel):
    """研究摘要响应"""
    summary: str = Field(description="LLM 生成的研究摘要")
    source: Literal["llm"] = Field(default="llm", description="摘要来源")

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
    weekly_sessions: int = Field(description="最近7天对话数")
    classes: list[StudentClassInfo] = Field(description="所属班级列表")

class StudentDailyActivity(BaseModel):
    """学生每日活动数据点"""
    date: str = Field(description="日期 YYYY-MM-DD")
    session_count: int = Field(description="当日对话数")


class StudentAnalysisResponse(BaseModel):
    """学生分析完整响应"""
    overview: StudentOverview = Field(description="学生概览")
    daily_activity: list[StudentDailyActivity] = Field(description="每日活动趋势")


# ===========================================================================
# 阶段分布 / 产出物完成（项目维度聚合）--响应模型

class ProjectStageStat(BaseModel):
    """单个项目单个阶段的进度统计"""
    stage_id: str = Field(description="阶段ID")
    order: int = Field(description="阶段顺序")
    title: str = Field(description="阶段标题")
    has_deliverable: bool = Field(description="该阶段是否配置了产出物")
    deliverable_title: str | None = Field(default=None, description="产出物标题")
    completed_count: int = Field(description="该项目该阶段已完成的学生数")
    in_progress_count: int = Field(description="进行中的学生数")
    started_count: int = Field(description="已开始(进行中或完成)的学生数")
    deliverable_submitted_count: int = Field(description="已提交产出物的学生数")
    deliverable_done_count: int = Field(description="产出物已达标的学生数")

class ProjectProgressSummary(BaseModel):
    """单个项目的阶段分布/产出物完成聚合"""
    project_id: UUID = Field(description="项目ID")
    project_name: str = Field(description="项目名称")
    student_count: int = Field(description="该项目有进度记录的学生数(分母)")
    stage_count: int = Field(description="项目阶段总数")
    stages: list[ProjectStageStat] = Field(description="各阶段进度统计")

class ProjectProgressResponse(BaseModel):
    """班级阶段分布/产出物完成响应（项目维度聚合，不限时间窗口）"""
    projects: list[ProjectProgressSummary] = Field(description="项目列表,按项目名排序")


# ===========================================================================
# 班级评价--响应模型

class EvaluationMetric(BaseModel):
    """单个维度下的证据指标（原始数值，便于报告展示与核验）"""
    label: str = Field(description="指标名")
    value: str = Field(description="指标值(字符串化)")

class ClassEvaluationDimension(BaseModel):
    """班级评价单维度评分"""
    dimension_id: str = Field(description="维度标识,如 participation/thinking/...")
    name: str = Field(description="维度名称,如 参与度")
    score: int = Field(description="评分 0-100")
    level: str = Field(description="等级: 高/中/低")
    metrics: list[EvaluationMetric] = Field(default_factory=list, description="证据指标")

class ClassEvaluationItem(BaseModel):
    """单个班级的班级评价（六维）"""
    class_id: UUID = Field(description="班级ID")
    class_name: str = Field(description="班级名称")
    dimensions: list[ClassEvaluationDimension] = Field(description="该班级已实现的评价维度")

class ClassEvaluationResponse(BaseModel):
    """班级评价响应。

    - 指定班级：classes 含 1 项（前端渲染六维卡片）
    - 全部班级：classes 含 N 项（前端渲染班级×维度横向对比表）
    - 班级不存在/教师无班级：classes 为空
    """
    days: int = Field(description="统计窗口天数(7/30)")
    classes: list[ClassEvaluationItem] = Field(description="各班级的评价维度(按班级解析顺序)")


# ===========================================================================
# 平时分（AI 评分）--请求/响应模型

class ScoringPromptResponse(BaseModel):
    """评分提示词响应"""
    prompt: str = Field(description="评分提示词(未自定义时为系统默认模板)")
    is_default: bool = Field(description="是否为系统默认模板(未自定义)")


class ScoringPromptUpdate(BaseModel):
    """评分提示词保存请求"""
    prompt: str = Field(min_length=1, max_length=20000, description="评分标准")


class ScoringGenerateRequest(BaseModel):
    """平时分生成请求"""
    class_id: UUID = Field(description="班级ID")
    since: date | None = Field(default=None, description="统计起始日期(含),缺省为全部历史")


class StudentScoreItem(BaseModel):
    """单个学生的平时分"""
    student_id: UUID
    name: str
    username: str
    score: int = Field(description="0-100")
    reason: str
    metrics: dict = Field(default_factory=dict, description="指标快照")


class ScoringResultResponse(BaseModel):
    """平时分结果"""
    class_id: UUID
    class_name: str
    since: date | None = None
    generated_at: datetime | None = None
    items: list[StudentScoreItem] = Field(default_factory=list, description="按分数降序")
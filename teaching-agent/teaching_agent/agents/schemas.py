"""LLM 结构化输出 schema。

DB 实体用 SQLModel（models.py），这里只定义 LLM 结构化输出的纯 Pydantic schema。
"""
from pydantic import BaseModel, Field


# === 知识图谱分析（入库时逐 chunk 调用）===


class KPSuggestion(BaseModel):
    """知识点建议。"""

    name: str = Field(description="知识点名称")
    is_new: bool = Field(description="True=新知识点, False=已有(复用)")
    description: str = Field(description="简短描述")


class EdgeSuggestion(BaseModel):
    """知识点间关系建议。"""

    source: str = Field(description="源知识点名称")
    target: str = Field(description="目标知识点名称")
    relation_type: str = Field(description="part_of / prerequisite / related / contrast")


class ChunkAnalysis(BaseModel):
    """单个 chunk 的知识图谱分析结果。"""

    knowledge_points: list[KPSuggestion]
    edges: list[EdgeSuggestion]


# === 出题 Agent ===


class QuizOutput(BaseModel):
    """出题 Agent 的结构化输出。"""

    q_type: str = Field(description="题型: single(单选) / multi(多选) / short(简答)")
    stem: str = Field(description="题干")
    options: list[str] = Field(description="选项列表，简答题为空列表")
    answer: str = Field(
        description="正确答案。单选填选项文本，多选填逗号分隔，简答填要点列表"
    )
    analysis: str = Field(description="解析说明")
    kp_name: str = Field(description="知识点名称")
    source_chunk_ids: list[str] = Field(description="关联的知识库片段 ID 列表")


# === 评估 Agent ===


class EvaluationOutput(BaseModel):
    """评估 Agent 的结构化输出。"""

    verdict: str = Field(description="判定: correct / partial / wrong")
    diagnosis: str = Field(description="错因诊断，答对时为空字符串")
    correct_answer: str = Field(description="正确答案，反馈给学生")
    analysis: str = Field(description="解析说明")
    follow_up_hint: str = Field(description="后续追问方向，供引导 Agent 参考")


# === 错题整理 Agent ===


class MistakeExtract(BaseModel):
    """错题提炼单项。"""

    question_id: str | None = Field(description="关联的 Question ID，无则 None")
    kp_name: str = Field(description="知识点名称")
    title: str = Field(description="题目摘要")
    wrong_answer: str = Field(description="学生的错误答案")
    correct_answer: str = Field(description="正确答案")
    diagnosis: str = Field(description="错因")
    source_chunk_ids: list[str] = Field(description="关联知识库片段 ID")


class ConsolidationOutput(BaseModel):
    """错题整理 Agent 的结构化输出。"""

    title: str = Field(description="会话标题，简洁如 'TCP三次握手学习'")
    summary: str = Field(description="会话摘要：学习内容、学生表现、薄弱点")
    mistakes: list[MistakeExtract] = Field(description="提炼的错题列表")
    profile_summary: str = Field(description="更新后的画像文本（增量更新）")
    weak_points: list[str] = Field(description="更新后的薄弱知识点名称列表")

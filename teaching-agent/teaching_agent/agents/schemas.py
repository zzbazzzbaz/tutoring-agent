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

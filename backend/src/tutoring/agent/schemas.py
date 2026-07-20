"""Agent 结构化输出 schema（Pydantic，非 SQLModel）。

present_question 工具的 args schema。从 tools.py 抽出，
使数据契约可独立 import/单测，不拖入 LightRAGClient 等工具依赖。
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuizOutput(BaseModel):
    """出题 LLM 的结构化输出 schema（present_question 工具 args）。"""

    q_type: Literal["single", "multi", "short"] = Field(description="题型：单选/多选/简答")
    stem: str = Field(description="题干")
    options: list[str] | None = Field(None, description="选项列表，short 题为 null")
    answer: str = Field(description="正确答案（single: 选项文本；multi: 'A,C,D'；short: 要点列表）")
    analysis: str = Field(description="题目解析")

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        """容错处理 LLM 返回的 options 格式。

        LLM 可能返回：
        - list[str]：正常
        - None：short 题无选项
        - str：可能是 JSON 编码的列表 '["A","B","C"]' 或单个选项文本
        - 其他：视为 None
        """
        if v is None:
            return None
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, str):
            import json as _json
            try:
                parsed = _json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
            return [v]
        return None

"""Agent 工具 args schema（Pydantic）。

@tool(args_schema=...) 使用的类型化参数 schema。独立于 tools.py，
使数据契约可独立 import/单测，不拖入 LightRAGClient 等工具依赖。
"""
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(description="检索关键词，需包含完整上下文（消除代词指代），如 'TCP三次握手' 而非 '它'")


class PresentQuestionArgs(BaseModel):
    topic: str = Field(description="知识点名称，如 TCP三次握手")
    q_type: Literal["single", "multi", "short"] = Field(description="题型：single=单选 multi=多选 short=简答")
    stem: str = Field(description="题干文本")
    options: list[str] | None = Field(
        None,
        description='选项列表数组，如 ["选项A","选项B","选项C","选项D"]。简答题传 null。必须传 JSON 数组，不要传字符串'
    )
    answer: str = Field(description="正确答案（single: 选项完整文本；multi: A,C,D；short: 要点）")
    analysis: str = Field(description="题目解析，说明考点和答案依据")

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
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
            return [v]
        return None

# 消息记录--Schema
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentMessageItem(BaseModel):
    """单条消息：学生提问或 AI 回复。"""

    role: Literal["student", "assistant"]
    content: str
    # 本轮学生提问是否命中知识库（仅 student 消息标记）
    knowledge_hit: bool = False


class AgentMessageBulkWriteRequest(BaseModel):
    """Agent Server 每回合结束后的消息批量写入请求。"""

    session_id: UUID
    messages: list[AgentMessageItem] = Field(default_factory=list)


class AgentMessageBulkWriteResponse(BaseModel):
    """写入结果。"""

    written: int

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
    # 本轮学生提问命中的知识库文档/知识点标识（chunk.file_path 或 entity.name 去重；仅 student 消息标记）
    knowledge_doc_ids: list[str] = Field(default_factory=list)


class AgentMessageBulkWriteRequest(BaseModel):
    """Agent Server 每回合结束后的消息批量写入请求。"""

    session_id: UUID
    messages: list[AgentMessageItem] = Field(default_factory=list)


class AgentMessageBulkWriteResponse(BaseModel):
    """写入结果。"""

    written: int

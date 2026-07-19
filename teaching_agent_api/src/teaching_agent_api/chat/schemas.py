"""Session、Message、Question、Chat 请求响应 schema。"""
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionCreate(BaseModel):
    """POST /sessions 的请求体。

    当 `mode='project'` 时 `project_id` 必填，且引用的 project 必须已
    处于 `published` 状态（在 service 中校验）。
    """

    mode: Literal["free", "project"]
    project_id: UUID | None = None

    @model_validator(mode="after")
    def check_project_id(self) -> Self:
        if self.mode == "project" and not self.project_id:
            raise ValueError("project_id is required when mode='project'")
        return self


class SessionOut(BaseModel):
    """返回给客户端的 Session 表示。

    `project_name` 仅在 session 的 project 已加载时填充。
    `from_attributes=True` 使我们可直接从 Session ORM 实例校验，但
    路由使用 `session_to_out_dict` 以额外添加 project_name。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    mode: str
    project_id: UUID | None = None
    project_name: str | None = None
    title: str | None
    status: str
    last_active_at: datetime
    created_at: datetime


class MessageOut(BaseModel):
    """聊天消息表示。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime


class QuestionOut(BaseModel):
    """题目 + 答题记录表示。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    topic: str
    q_type: str
    stem: str
    options: list[str] | None = None
    answer: str
    analysis: str | None = None
    status: str
    user_answer: str | None = None
    verdict: str | None = None
    diagnosis: str | None = None
    created_at: datetime
    answered_at: datetime | None = None


class SendMessageRequest(BaseModel):
    """POST /chat/sessions/{id}/messages 请求体。"""

    content: str = Field(min_length=1)


class QuizResumeRequest(BaseModel):
    """POST /chat/sessions/{id}/quiz/resume 请求体。"""

    action: Literal["answer", "skip"]
    answer: str | None = None

    @model_validator(mode="after")
    def check_answer_required(self):
        """action='answer' 时 answer 必填。"""
        if self.action == "answer" and not self.answer:
            raise ValueError("answer is required when action='answer'")
        return self

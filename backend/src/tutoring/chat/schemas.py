from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionCreate(BaseModel):

    mode: Literal["free", "project"]
    project_id: UUID | None = None

    @model_validator(mode="after")
    def check_project_id(self) -> Self:
        if self.mode == "project" and not self.project_id:
            raise ValueError("project_id is required when mode='project'")
        return self


class SessionOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    mode: str
    project_id: UUID | None = None
    project_name: str | None = None
    title: str | None
    last_active_at: datetime
    created_at: datetime


class MessageOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str
    content: str
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    created_at: datetime


class QuestionOut(BaseModel):

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
    created_at: datetime
    answered_at: datetime | None = None


class SendMessageRequest(BaseModel):

    content: str = Field(min_length=1)
    retry: bool = False


class QuizResumeRequest(BaseModel):

    action: Literal["answer", "skip"]
    answer: str | None = None

    @model_validator(mode="after")
    def check_answer_required(self):
        """action='answer' 时 answer 必填。"""
        if self.action == "answer" and not self.answer:
            raise ValueError("answer is required when action='answer'")
        return self


class HistoryItemOut(BaseModel):
    type: str
    data: dict


class HistoryOut(BaseModel):
    items: list[HistoryItemOut]
    pending_quiz: dict | None = None
    processing: bool = False

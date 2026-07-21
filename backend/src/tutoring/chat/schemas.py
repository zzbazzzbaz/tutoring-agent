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


class ChatEventOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    type: str
    created_at: datetime
    content: str | None = None
    data: dict | None = None
    status: str | None = None
    answered_at: datetime | None = None


class HistoryOut(BaseModel):
    items: list[ChatEventOut]
    pending_quiz: ChatEventOut | None = None
    processing: bool = False


class SendMessageRequest(BaseModel):

    content: str = Field(min_length=1)
    retry: bool = False


class QuizResumeRequest(BaseModel):

    action: Literal["answer", "skip"]
    answer: str | None = None

    @model_validator(mode="after")
    def check_answer_required(self):
        if self.action == "answer" and not self.answer:
            raise ValueError("answer is required when action='answer'")
        return self

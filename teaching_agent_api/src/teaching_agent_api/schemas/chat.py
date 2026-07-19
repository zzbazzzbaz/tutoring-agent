"""Chat 端点的请求 schema。"""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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

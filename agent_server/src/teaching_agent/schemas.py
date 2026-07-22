import json
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mode: Literal["free", "project"]
    course_name: str = Field(min_length=1)
    project_name: str = ""
    project_background_md: str = ""

    @model_validator(mode="after")
    def validate_mode_fields(self) -> Self:
        if self.mode == "project" and not self.project_name:
            raise ValueError("project mode requires project_name")
        if self.mode == "free" and (self.project_name or self.project_background_md):
            raise ValueError("free mode cannot contain project fields")
        return self


class AuthorizedPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str
    role: Literal["student", "teacher"]
    name: str
    session_id: UUID | None = None
    session_access: Literal["identity", "read", "run"] = "identity"
    agent_context: AgentContextV1 | None = None


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        description="检索关键词，需包含完整上下文（消除代词指代），如 'TCP三次握手' 而非 '它'"
    )


class PresentQuestionArgs(BaseModel):
    topic: str = Field(description="知识点名称，如 TCP三次握手")
    q_type: Literal["single", "multi", "short"] = Field(
        description="题型：single=单选 multi=多选 short=简答"
    )
    stem: str = Field(description="题干文本")
    options: list[str] | None = Field(
        None,
        description='选项列表数组，如 ["选项A","选项B","选项C","选项D"]。简答题传 null。',
    )

    @field_validator("options", mode="before")
    @classmethod
    def coerce_options(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
            return [value]
        return None


class QuizResume(BaseModel):
    action: Literal["answer", "skip"] = "answer"
    answer: str = ""

    @model_validator(mode="before")
    @classmethod
    def coerce_resume(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                pass
        return value

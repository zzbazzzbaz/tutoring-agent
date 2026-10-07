from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    mainline: dict[str, Any] | None = None
    status: Literal["draft", "published"] = "draft"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    background_md: str | None = Field(default=None, min_length=1)
    mainline: dict[str, Any] | None = None
    status: Literal["draft", "published"] | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    background_md: str
    mainline: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class AgentCaseDraftStage(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    guide: str = ""
    student_desc: str = ""
    deliverable_title: str = ""
    deliverable_instructions: str = ""

    @model_validator(mode="after")
    def check_deliverable(self) -> Self:
        if self.deliverable_title and not self.deliverable_instructions:
            raise ValueError("产出物名称与产出物要求必须同时提供")
        return self


class AgentCaseDraftIn(BaseModel):
    project_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    stages: list[AgentCaseDraftStage] = Field(min_length=1, max_length=8)


class AgentCaseDraftOut(BaseModel):
    project_id: UUID
    project_name: str
    stage_count: int
    created: bool

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


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

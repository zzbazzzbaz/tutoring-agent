from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):

    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    status: Literal["draft", "published"] = "draft"


class ProjectUpdate(BaseModel):

    name: str | None = Field(default=None, min_length=1, max_length=200)
    background_md: str | None = Field(default=None, min_length=1)
    status: Literal["draft", "published"] | None = None


class ProjectOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    background_md: str
    status: str
    created_at: datetime
    updated_at: datetime

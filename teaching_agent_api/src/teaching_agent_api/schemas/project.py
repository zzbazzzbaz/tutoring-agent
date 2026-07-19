"""Project 资源的 Pydantic schema。"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """POST /projects 的请求体。"""

    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    status: Literal["draft", "published"] = "draft"


class ProjectUpdate(BaseModel):
    """PATCH /projects/{id} 的请求体。所有字段可选。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    background_md: str | None = Field(default=None, min_length=1)
    status: Literal["draft", "published"] | None = None


class ProjectOut(BaseModel):
    """返回给客户端的 Project 表示。

    `from_attributes=True` 使我们可直接用 SQLModel `Project` 实例调用
    `ProjectOut.model_validate(orm_obj)`。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    background_md: str
    status: str
    created_at: datetime
    updated_at: datetime

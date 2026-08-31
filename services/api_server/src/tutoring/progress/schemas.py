# 会话学习进度--Schema
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentProgressUpdate(BaseModel):
    """Agent Server 内部写入/更新会话学习进度请求。

    progress: {stage_id: {"status": "pending|in_progress|completed",
                           "deliverable": str | None,
                           "deliverable_done": bool}}
    """

    session_id: UUID
    progress: dict[str, Any]


class AgentProgressUpdateResponse(BaseModel):
    updated: bool


class SessionProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    progress: dict[str, Any]
    updated_at: datetime | None = None

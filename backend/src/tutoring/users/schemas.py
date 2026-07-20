from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: str
    name: str
    created_at: datetime


class ImportResult(BaseModel):
    total: int
    created: int
    skipped: int
    errors: list[str]

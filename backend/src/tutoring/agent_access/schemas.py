from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentAuthorizeRequest(BaseModel):
    session_id: UUID | None = None
    access: Literal["identity", "read", "run"]
    touch: bool = False

    @model_validator(mode="after")
    def validate_access(self) -> Self:
        if self.access == "identity" and self.session_id is not None:
            raise ValueError("identity access cannot include session_id")
        if self.access != "identity" and self.session_id is None:
            raise ValueError("session_id is required for thread access")
        if self.touch and self.access != "run":
            raise ValueError("only run access can touch a session")
        return self


class AgentContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mode: Literal["free", "project"]
    course_name: str = Field(min_length=1)
    project_name: str = ""
    project_background_md: str = ""


class AgentAuthorizeResponse(BaseModel):
    identity: str
    role: Literal["student", "teacher"]
    name: str
    session_id: UUID | None = None
    session_access: Literal["identity", "read", "run"]
    agent_context: AgentContextV1 | None = None

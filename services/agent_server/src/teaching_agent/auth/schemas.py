from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class AgentContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mode: Literal["free", "project", "case_design"]
    project_name: str = ""
    project_id: str = ""
    project_background_md: str = ""
    project_mainline: str = ""

    @model_validator(mode="after")
    def validate_mode_fields(self) -> Self:
        if self.mode == "project" and not self.project_name:
            raise ValueError("project mode requires project_name")
        if self.mode != "project" and (self.project_name or self.project_background_md):
            raise ValueError("only project mode can contain project fields")
        return self


class AuthorizedPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str
    role: Literal["student", "teacher"]
    name: str
    session_id: UUID | None = None
    session_access: Literal["identity", "read", "run"] = "identity"
    agent_context: AgentContextV1 | None = None

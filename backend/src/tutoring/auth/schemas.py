from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: str
    name: str


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


class MeResponse(UserPublic):
    pass


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

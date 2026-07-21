import uuid
from datetime import datetime

from sqlalchemy import JSON, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlmodel import SQLModel, Field, Column, Relationship


class User(SQLModel, table=True):
    """用户表：学生 / 教师。账号由后台创建。"""
    __tablename__ = "user"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    username: str = Field(max_length=100, unique=True, index=True)
    password_hash: str = Field(sa_column=Column(Text))
    role: str = Field(max_length=20, index=True)  # student/teacher
    name: str = Field(max_length=100)
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))

    sessions: list["Session"] = Relationship(back_populates="user", cascade_delete=True)
    tokens: list["AuthToken"] = Relationship(back_populates="user", cascade_delete=True)


class AuthToken(SQLModel, table=True):
    """登录 token。无过期，登出 = 删除行。"""
    __tablename__ = "auth_token"

    token: str = Field(max_length=64, sa_column=Column(Text, primary_key=True))
    user_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
        ),
    )
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))

    user: "User" = Relationship(back_populates="tokens")


class Project(SQLModel, table=True):
    """Project 元数据；在 project 模式下注入 agent 系统 prompt。"""
    __tablename__ = "project"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    name: str = Field(max_length=200, unique=True, index=True)
    background_md: str = Field(sa_column=Column(Text))
    status: str = Field(default="draft", max_length=20, index=True)  # draft/published
    deleted_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    updated_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()))

    sessions: list["Session"] = Relationship(back_populates="project")


class Session(SQLModel, table=True):
    """聊天 session。id 复用为 LangGraph thread_id。"""
    __tablename__ = "session"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
        ),
    )
    mode: str = Field(max_length=20)  # free/project
    project_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("project.id", ondelete="SET NULL"),
            index=True,
        ),
    )
    title: str | None = Field(default=None, max_length=200)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))
    last_active_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    updated_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()))

    project: Project | None = Relationship(back_populates="sessions")
    user: User | None = Relationship(back_populates="sessions")
    events: list["ChatEvent"] = Relationship(back_populates="session", cascade_delete=True)


class ChatEvent(SQLModel, table=True):
    """统一聊天事件表。type 区分 user/agent/tool/quiz。"""
    __tablename__ = "chat_event"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    session_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("session.id", ondelete="CASCADE"),
            index=True,
        ),
    )
    type: str = Field(max_length=20)  # user/agent/tool/quiz
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    content: str | None = Field(default=None, sa_column=Column(Text))
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str | None = Field(default=None, max_length=20)  # quiz: pending/answered/skipped
    answered_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    session: "Session" = Relationship(back_populates="events")

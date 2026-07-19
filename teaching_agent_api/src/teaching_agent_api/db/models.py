import uuid
from datetime import datetime

from sqlalchemy import JSON, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlmodel import SQLModel, Field, Column, Relationship


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
    user_id: str = Field(default="demo-student", max_length=100, index=True)
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
    status: str = Field(default="active", max_length=20, index=True)  # active/ended
    last_active_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    updated_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()))

    project: Project | None = Relationship(back_populates="sessions")
    messages: list["Message"] = Relationship(back_populates="session", cascade_delete=True)
    questions: list["Question"] = Relationship(back_populates="session", cascade_delete=True)


class Message(SQLModel, table=True):
    """业务查询的聊天消息。LangGraph 自身的消息历史位于 checkpoint 表中。"""
    __tablename__ = "message"

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
    role: str = Field(max_length=20)  # user/agent
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))

    session: "Session" = Relationship(back_populates="messages")


class Question(SQLModel, table=True):
    """测验题目 + 答题记录（合并为 1:1）。status 字段区分
    pending/answered/skipped。"""
    __tablename__ = "question"

    # === 题目字段（在 interrupt 前设置）===
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
    topic: str = Field(max_length=200, index=True)
    q_type: str = Field(max_length=20)  # single/multi/short
    stem: str = Field(sa_column=Column(Text))
    options: list | None = Field(default=None, sa_column=Column(JSON))  # short 类型时为 null
    answer: str = Field(sa_column=Column(Text))  # 正确答案
    analysis: str | None = Field(default=None, sa_column=Column(Text))  # 题目解析

    # === 状态 ===
    status: str = Field(default="pending", max_length=20, index=True)  # pending/answered/skipped

    # === 答题字段（在 resume 时设置；nullable）===
    user_answer: str | None = Field(default=None, sa_column=Column(Text))
    verdict: str | None = Field(default=None, max_length=20)  # correct/partial/wrong
    diagnosis: str | None = Field(default=None, sa_column=Column(Text))

    # === 时间戳 ===
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    answered_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    session: "Session" = Relationship(back_populates="questions")

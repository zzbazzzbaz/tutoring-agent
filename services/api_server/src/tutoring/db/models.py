import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Column, Field, Relationship, SQLModel


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
    avatar_url: str | None = Field(default=None, max_length=500)#头像地址
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    # 删除时间(软删除)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))
    # 删除原因
    deleted_reason: str | None = Field(default=None, max_length=500)
    # 删除人id
    deleted_by: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True)))

    sessions: list["Session"] = Relationship(back_populates="user", cascade_delete=True)
    tokens: list["AuthToken"] = Relationship(back_populates="user", cascade_delete=True)

class Class(SQLModel, table=True):
    """班级表"""

    __tablename__ = "class"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID, primary_key=True),
    )
    #年级
    grade: str = Field(max_length=50,index=True)
    #班级名称
    classname: str = Field(max_length=20,index=True)
    #关联教师id
    teacher_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID,
            ForeignKey("user.id", ondelete="RESTRICT"),
            index=True,
        ),
    )
    #状态(active正常/archived归档)
    status: str = Field(default="active",max_length=20,index=True)
    #创建时间
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    #修改时间
    updated_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    )
    #删除时间(软删除)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    teacher: User | None = Relationship(
        sa_relationship_kwargs={"lazy": "joined"}
    )
    students: list["ClassStudent"] = Relationship(back_populates="class_", cascade_delete=True)

class ClassStudent(SQLModel, table=True):
    """班级学生关联表"""
    __tablename__ = "class_student"
    #关联class表
    class_id:uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("class.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    #关联user表
    user_id:uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
            index=True,
        )
    )
    #学生加入时间
    joined_at:datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    class_: "Class" = Relationship(back_populates="students")
    user: User | None = Relationship(
        sa_relationship_kwargs={"lazy": "joined"}
    )


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
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )

    user: "User" = Relationship(back_populates="tokens")


class Project(SQLModel, table=True):
    """Project 元数据；在 project 模式下注入 agent 系统 prompt。"""

    __tablename__ = "project"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    name: str = Field(max_length=200, unique=True, index=True)
    background_md: str = Field(sa_column=Column(Text))#背景信息
    # 结构化学习主线（老师配置）：{"objective": str, "stages": [{id, order, title, guide, deliverable?}]}
    mainline: dict | None = Field(default=None, sa_column=Column(JSONB))
    status: str = Field(default="draft", max_length=20, index=True)  # draft/published
    deleted_at: datetime | None = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    )

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
    mode: str = Field(max_length=20)  # 会话模式:自由学习free/项目project
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
    last_active_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    project: Project | None = Relationship(back_populates="sessions")
    user: User | None = Relationship(back_populates="sessions")
    messages: list["Message"] = Relationship(back_populates="session", cascade_delete=True)


class Message(SQLModel, table=True):
    """消息表：记录每句学生/AI 发言。用于互动明细 / 知识命中率等消息级统计。

    说明：
    - `role` 取值：student（学生发起）/ assistant（AI 回复）
    - `knowledge_hit`：本轮学生提问是否命中知识库（是否调用过检索知识工具）
    - `knowledge_doc_ids`：本轮学生提问命中的知识库文档/知识点标识（优先 chunk.file_path，
      缺省时用 entity.name，去重），用于"知识点覆盖广度"统计；仅 student 消息标记
    - 落库由 Agent Server 每回合结束写入，本表数据自启用后开始累积
    """

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
    role: str = Field(max_length=20, index=True)  # student / assistant
    content: str = Field(sa_column=Column(Text))
    # 本轮学生提问是否命中知识库
    knowledge_hit: bool = Field(default=False)
    # 本轮学生提问命中的知识库文档/知识点标识（JSONB 字符串数组，去重）
    knowledge_doc_ids: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )

    session: Session | None = Relationship(back_populates="messages")


class SessionProgress(SQLModel, table=True):
    """会话级学习进度（每个会话独立，不跨会话累积）。

    progress 结构：{stage_id: {"status": "pending|in_progress|completed",
                                "deliverable": str | None, "deliverable_done": bool}}
    """

    __tablename__ = "session_progress"

    session_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("session.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    progress: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    updated_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    session: Session | None = Relationship()

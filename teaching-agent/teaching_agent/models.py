"""全部 SQLModel 表定义。

12 张业务表，按依赖顺序定义。pgvector Vector 类型通过 sa_column 注入，
JSON 字段同理。所有主键为 str（UUID）。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, JSON, DateTime
from pgvector.sqlalchemy import Vector
from sqlmodel import SQLModel, Field


def _now() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# 1. 项目表
class Project(SQLModel, table=True):
    """学习项目，用于项目式学习场景。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    background_md: str = Field(default="")
    status: str = Field(default="draft")  # draft / published / archived
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 2. 知识库文档表
class KBDocument(SQLModel, table=True):
    """知识库文档元数据。scope: course（课程级）/ project（项目级）。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    scope: str  # course / project
    project_id: str | None = Field(default=None, foreign_key="project.id")
    filename: str
    status: str = Field(default="processing")  # processing / ready / failed
    chunk_count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 3. 知识片段表（含向量）
class Chunk(SQLModel, table=True):
    """知识片段，含 1024 维 embedding 向量。HNSW 索引在 init_db 后用 raw SQL 创建。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="kbdocument.id")
    content: str
    heading_path: str
    chunk_index: int
    scope: str  # course / project
    project_id: str | None = Field(default=None, foreign_key="project.id")
    embedding: list[float] = Field(sa_column=Column(Vector(1024)))
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 4. 知识点表（图节点）
class KnowledgePoint(SQLModel, table=True):
    """知识点，由 LLM 逐 chunk 分析识别，非 heading 自动生成。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(unique=True)
    description: str = Field(default="")
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 5. 知识点边表（图边）
class KnowledgeEdge(SQLModel, table=True):
    """知识点间关系边。relation_type: part_of / prerequisite / related / contrast。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    source_id: str = Field(foreign_key="knowledgepoint.id")
    target_id: str = Field(foreign_key="knowledgepoint.id")
    relation_type: str  # part_of / prerequisite / related / contrast


# 6. Chunk-KP 关联表（N:N）
class ChunkKnowledgePoint(SQLModel, table=True):
    """知识片段与知识点的多对多关联。"""

    chunk_id: str = Field(foreign_key="chunk.id", primary_key=True)
    kp_id: str = Field(foreign_key="knowledgepoint.id", primary_key=True)


# 7. 会话表
class Session(SQLModel, table=True):
    """学习会话。type: free / project / review; status: active / ended。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(default="demo-student")
    type: str  # free / project / review
    project_id: str | None = Field(default=None, foreign_key="project.id")
    mistake_id: str | None = Field(default=None, foreign_key="mistakeitem.id")
    title: str = Field(default="")
    summary: str = Field(default="")
    status: str = Field(default="active")  # active / ended
    last_active_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    ended_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


# 8. 消息表
class Message(SQLModel, table=True):
    """对话消息。role: user / agent; 业务查询用，checkpointer 管编排状态。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="session.id")
    role: str  # user / agent
    content: str
    question_id: str | None = Field(default=None, foreign_key="question.id")
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 9. 题目表
class Question(SQLModel, table=True):
    """题目。q_type: single / multi / short; status: pending / answered / skipped。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="session.id")
    kp_id: str | None = Field(default=None, foreign_key="knowledgepoint.id")
    q_type: str  # single / multi / short
    stem: str
    options: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    answer: str
    analysis: str = Field(default="")
    source_chunk_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="pending")  # pending / answered / skipped
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 10. 答题记录表
class AnswerRecord(SQLModel, table=True):
    """学生答题记录。verdict: correct / partial / wrong。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    question_id: str = Field(foreign_key="question.id")
    user_id: str = Field(default="demo-student")
    session_id: str = Field(foreign_key="session.id")
    user_answer: str
    verdict: str  # correct / partial / wrong
    diagnosis: str = Field(default="")
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )


# 11. 错题表
class MistakeItem(SQLModel, table=True):
    """错题本条目。mastery_status: unmastered / reviewing / mastered。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(default="demo-student")
    question_id: str | None = Field(default=None, foreign_key="question.id")
    kp_id: str | None = Field(default=None, foreign_key="knowledgepoint.id")
    title: str
    wrong_answer: str
    correct_answer: str
    diagnosis: str = Field(default="")
    source_chunk_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    mastery_status: str = Field(default="unmastered")  # unmastered / reviewing / mastered
    source_session_id: str = Field(foreign_key="session.id")
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


# 12. 学生画像表
class StudentProfile(SQLModel, table=True):
    """学生画像，跨会话记忆。weak_points: [{kp_id, score, misconception}]。"""

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(unique=True)
    summary: str = Field(default="")
    weak_points: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    learning_style: str = Field(default="未知")
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

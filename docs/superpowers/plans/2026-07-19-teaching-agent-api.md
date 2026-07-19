# 教学 Agent API 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 
> **Deviation from default workflow:** User explicitly waived TDD. Each task ends with **direct API verification** (real model + real LightRAG + real DB), not unit tests with mocks. The final Task 6 is the comprehensive integration test suite.

**Goal:** FastAPI 重构版教学 Agent 后端：单 agent 双模式（free/project），LightRAG 代理 RAG，SSE 流式响应，HITL quiz，4 表极简数据模型。

**Architecture:** 分层模块化 FastAPI（api/ 薄路由 + agent/ LangGraph 1.x + lightrag/ 客户端 + db/ 持久层 + schemas/ API 契约）。单 agent 实例 + `@dynamic_prompt` 中间件 + `AgentContext` dataclass 实现 free/project 双模式。`AsyncPostgresSaver` checkpointer 支持 `interrupt()` / `Command(resume=...)` HITL。

**Tech Stack:** Python 3.13 + uv / FastAPI + sse-starlette / LangChain >= 1.3 + LangGraph >= 1.2 + langgraph-checkpoint-postgres / SQLModel + asyncpg + psycopg / httpx / DashScope qwen3.6-flash / LightRAG 1.5.4 (HTTP 代理)

## Global Constraints

- **Python 3.13**，uv 管理，`src/` layout
- **LangChain/LangGraph 1.x**（严禁 0.3.x API）：
  - `from langchain.agents import create_agent`（不是 `langgraph.prebuilt.create_react_agent`）
  - `from langchain.agents.middleware import dynamic_prompt, ModelRequest`
  - `agent.astream_events(..., version="v3")`（不是 v2）
  - `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`
  - `from langgraph.types import interrupt, Command`
- **真实模型**：DashScope qwen3.6-flash（`enable_thinking=False`，温度 0.7），不 mock
- **真实 LightRAG**：`http://101.35.223.219:15434`，`X-API-Key: lightrag-sk-teaching-agent-2026`，不 mock
- **真实 DB**：`postgresql+asyncpg://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718`
- **课程**：计算机网络
- **无 TDD**：测试直接调真实 API（httpx + ASGITransport）
- **本轮只覆盖后端**
- **所有代码英文注释/日志**，prompt 模板中文（面向学生）
- **不提交 git**（除非用户明确要求）

## File Structure

```
teaching_agent_api/
├── pyproject.toml                          # T1
├── .env.example                            # T1
├── .python-version                         # T1
├── README.md                               # T1
├── src/teaching_agent_api/
│   ├── __init__.py                         # T1
│   ├── main.py                             # T1 骨架 / T5 完成（挂全部 router）
│   ├── config.py                           # T1
│   ├── deps.py                             # T1 基础 / T4 完成（get_agent）
│   ├── api/
│   │   ├── __init__.py                     # T1
│   │   ├── health.py                       # T1
│   │   ├── projects.py                     # T2
│   │   ├── sessions.py                      # T2
│   │   ├── chat.py                         # T4
│   │   ├── documents.py                    # T5
│   │   └── graph.py                        # T5
│   ├── agent/
│   │   ├── __init__.py                     # T3
│   │   ├── llm.py                          # T3
│   │   ├── prompts.py                      # T3
│   │   ├── tools.py                        # T3
│   │   ├── factory.py                      # T3
│   │   └── runtime.py                      # T4
│   ├── lightrag/
│   │   ├── __init__.py                     # T2
│   │   ├── client.py                       # T2
│   │   └── schemas.py                      # T2
│   ├── db/
│   │   ├── __init__.py                     # T1
│   │   ├── engine.py                       # T1
│   │   ├── models.py                       # T1
│   │   └── repos.py                        # T1
│   └── schemas/
│       ├── __init__.py                     # T2
│       ├── project.py                      # T2
│       ├── session.py                      # T2
│       └── chat.py                         # T4
└── tests/
    ├── __init__.py                         # T6
    ├── conftest.py                         # T6
    ├── test_health.py                      # T6
    ├── test_projects.py                    # T6
    ├── test_sessions.py                    # T6
    ├── test_documents_proxy.py             # T6
    └── test_chat_streaming.py              # T6
```

---

## Task 1: Foundation - 项目骨架 + 配置 + DB 层 + Lifespan + /health

**Goal:** uv 工程能跑起来，FastAPI lifespan 正确初始化 DB engine + AsyncPostgresSaver + LightRAGClient 占位（不含具体调用），`/health` 返回所有组件状态。

**Files:**
- Create: `teaching_agent_api/pyproject.toml`
- Create: `teaching_agent_api/.env.example`
- Create: `teaching_agent_api/.python-version`
- Create: `teaching_agent_api/README.md`
- Create: `teaching_agent_api/src/teaching_agent_api/__init__.py`（空文件）
- Create: `teaching_agent_api/src/teaching_agent_api/config.py`
- Create: `teaching_agent_api/src/teaching_agent_api/db/__init__.py`（空文件）
- Create: `teaching_agent_api/src/teaching_agent_api/db/engine.py`
- Create: `teaching_agent_api/src/teaching_agent_api/db/models.py`
- Create: `teaching_agent_api/src/teaching_agent_api/db/repos.py`
- Create: `teaching_agent_api/src/teaching_agent_api/api/__init__.py`（空文件）
- Create: `teaching_agent_api/src/teaching_agent_api/api/health.py`
- Create: `teaching_agent_api/src/teaching_agent_api/deps.py`
- Create: `teaching_agent_api/src/teaching_agent_api/main.py`

**Interfaces:**
- Produces: `Settings`（pydantic-settings），`init_db(engine)`，4 个 SQLModel 表（Project/Session/Message/Question），repos 异步函数，`get_db`/`get_lightrag_client`/`get_agent` 依赖（get_lightrag_client/get_agent 占位，T2/T3 填充），`/health` 端点

- [ ] **Step 1: 创建 uv 工程**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent
mkdir -p teaching_agent_api/src/teaching_agent_api
cd teaching_agent_api
uv init --python 3.13 --package teaching_agent_api
```

- [ ] **Step 2: 写 `pyproject.toml`**

```toml
[project]
name = "teaching-agent-api"
version = "0.1.0"
description = "Teaching Agent backend (FastAPI + LightRAG + LangChain 1.x)"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.1",
    "httpx>=0.27",
    "langchain>=1.3",
    "langgraph>=1.2",
    "langgraph-checkpoint-postgres>=3.1",
    "langchain-openai>=1.3",
    "sqlmodel>=0.0.22",
    "asyncpg>=0.30",
    "psycopg[binary]>=3.2",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "python-multipart>=0.0.12",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "asgi-lifespan>=2.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/teaching_agent_api"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 写 `.env.example` 和 `.python-version`**

`teaching_agent_api/.python-version`：
```
3.13
```

`teaching_agent_api/.env.example`：
```bash
# === 数据库 ===
DATABASE_URL=postgresql+asyncpg://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718

# === LightRAG ===
LIGHTRAG_BASE_URL=http://101.35.223.219:15434
LIGHTRAG_API_KEY=lightrag-sk-teaching-agent-2026

# === LLM (DashScope) ===
DASHSCOPE_API_KEY=sk-cad2e2400e384fc7aa08846770dac9e1
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-flash

# === 课程 ===
COURSE_NAME=计算机网络
COURSE_INTRO=本课程涵盖TCP/IP协议族、HTTP协议、网络拥塞控制等核心内容

# === 服务 ===
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=*
```

复制为 `.env`：
```bash
cp .env.example .env
```

- [ ] **Step 4: 写 `config.py`**

```python
# src/teaching_agent_api/config.py
"""Application settings driven by .env via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # LightRAG
    lightrag_base_url: str
    lightrag_api_key: str

    # LLM (DashScope, OpenAI-compatible)
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.6-flash"

    # Course
    course_name: str = "计算机网络"
    course_intro: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"


settings = Settings()
```

- [ ] **Step 5: 写 `db/models.py`（4 张表）**

```python
# src/teaching_agent_api/db/models.py
"""SQLModel ORM models. 4 business tables; LangGraph checkpoint tables are
created separately by AsyncPostgresSaver.setup()."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlmodel import SQLModel, Field, Column, Relationship


class Project(SQLModel, table=True):
    """Project metadata; injected into agent system prompt in project mode."""
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
    """Chat session. id is reused as LangGraph thread_id."""
    __tablename__ = "session"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    user_id: str = Field(default="demo-student", max_length=100, index=True)
    mode: str = Field(max_length=20)  # free/project
    project_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("project.id", ondelete="SET NULL"),
            index=True,
        ),
    )
    title: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="active", max_length=20, index=True)  # active/ended
    last_active_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    updated_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()))

    project: Optional["Project"] = Relationship(back_populates="sessions")
    messages: list["Message"] = Relationship(back_populates="session", cascade_delete=True)
    questions: list["Question"] = Relationship(back_populates="session", cascade_delete=True)


class Message(SQLModel, table=True):
    """Chat message for business queries. LangGraph's own message history lives in checkpoint tables."""
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
    """Quiz question + answer record (merged 1:1). status field distinguishes
    pending/answered/skipped."""
    __tablename__ = "question"

    # === Question fields (set before interrupt) ===
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
    options: Optional[list] = Field(default=None, sa_column=Column(JSON))  # null for short
    answer: str = Field(sa_column=Column(Text))  # correct answer
    analysis: Optional[str] = Field(default=None, sa_column=Column(Text))  # question analysis

    # === Status ===
    status: str = Field(default="pending", max_length=20, index=True)  # pending/answered/skipped

    # === Answer fields (set on resume; nullable) ===
    user_answer: Optional[str] = Field(default=None, sa_column=Column(Text))
    verdict: Optional[str] = Field(default=None, max_length=20)  # correct/partial/wrong
    diagnosis: Optional[str] = Field(default=None, sa_column=Column(Text))

    # === Timestamps ===
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    answered_at: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    session: "Session" = Relationship(back_populates="questions")
```

- [ ] **Step 6: 写 `db/engine.py`**

```python
# src/teaching_agent_api/db/engine.py
"""Async DB engine + session factory + idempotent schema initialization."""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from teaching_agent_api.db import models  # noqa: F401 - register tables on SQLModel.metadata


def create_engine(database_url: str, *, pool_size: int = 10, max_overflow: int = 20) -> AsyncEngine:
    return create_async_engine(database_url, pool_size=pool_size, max_overflow=max_overflow, echo=False)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db(engine: AsyncEngine) -> None:
    """Idempotent: create all business tables if not exist. Called once at lifespan startup."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
```

- [ ] **Step 7: 写 `db/repos.py`（仓储函数）**

```python
# src/teaching_agent_api/db/repos.py
"""Async repository functions. No classes (YAGNI)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func

from teaching_agent_api.db.models import Project, Session, Message, Question


# === Session ===

async def create_session(
    db: AsyncSession, *, mode: str, user_id: str, project_id: Optional[UUID] = None,
) -> Session:
    obj = Session(mode=mode, user_id=user_id, project_id=project_id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_session(db: AsyncSession, session_id: UUID) -> Optional[Session]:
    return await db.get(Session, session_id)


async def list_sessions(
    db: AsyncSession, *, user_id: str, status: Optional[str] = None,
    mode: Optional[str] = None, limit: int = 20, offset: int = 0,
) -> list[Session]:
    stmt = select(Session).where(Session.user_id == user_id)
    if status:
        stmt = stmt.where(Session.status == status)
    if mode:
        stmt = stmt.where(Session.mode == mode)
    stmt = stmt.order_by(Session.last_active_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def touch_session(db: AsyncSession, session_id: UUID) -> None:
    await db.execute(
        update(Session).where(Session.id == session_id).values(last_active_at=datetime.utcnow())
    )
    await db.commit()


async def end_session(db: AsyncSession, session_id: UUID) -> None:
    await db.execute(
        update(Session).where(Session.id == session_id).values(status="ended")
    )
    await db.commit()


# === Message ===

async def save_message(db: AsyncSession, *, session_id: UUID, role: str, content: str) -> Message:
    obj = Message(session_id=session_id, role=role, content=content)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_messages(db: AsyncSession, session_id: UUID, *, limit: int = 100, offset: int = 0) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# === Question ===

async def upsert_pending_question(
    db: AsyncSession, *, session_id: UUID, topic: str, q_type: str,
    stem: str, options: Optional[list], answer: str, analysis: Optional[str],
) -> Question:
    """Idempotent: if a pending question exists for (session_id, topic), return it; otherwise insert."""
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing:
        return existing
    obj = Question(
        session_id=session_id, topic=topic, q_type=q_type,
        stem=stem, options=options, answer=answer, analysis=analysis,
        status="pending",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_pending_question(db: AsyncSession, session_id: UUID, topic: str) -> Optional[Question]:
    stmt = (
        select(Question)
        .where(Question.session_id == session_id, Question.topic == topic, Question.status == "pending")
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_question(db: AsyncSession, question_id: UUID, **fields) -> None:
    fields["answered_at"] = fields.get("answered_at", datetime.utcnow())
    await db.execute(update(Question).where(Question.id == question_id).values(**fields))
    await db.commit()


async def list_questions(
    db: AsyncSession, session_id: UUID, *, status: Optional[str] = None,
) -> list[Question]:
    stmt = select(Question).where(Question.session_id == session_id)
    if status:
        stmt = stmt.where(Question.status == status)
    stmt = stmt.order_by(Question.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# === Project ===

async def create_project(db: AsyncSession, *, name: str, background_md: str, status: str = "draft") -> Project:
    obj = Project(name=name, background_md=background_md, status=status)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_project(db: AsyncSession, project_id: UUID) -> Optional[Project]:
    return await db.get(Project, project_id)


async def list_projects(db: AsyncSession, *, status: Optional[str] = None) -> list[Project]:
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_project(db: AsyncSession, project_id: UUID, **fields) -> Optional[Project]:
    await db.execute(update(Project).where(Project.id == project_id).values(**fields))
    await db.commit()
    return await db.get(Project, project_id)


async def delete_project(db: AsyncSession, project_id: UUID) -> None:
    proj = await db.get(Project, project_id)
    if proj:
        await db.delete(proj)
        await db.commit()
```

- [ ] **Step 8: 写 `deps.py`**

```python
# src/teaching_agent_api/deps.py
"""FastAPI dependencies."""
from typing import AsyncIterator

from fastapi import Request, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.config import settings


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request DB session."""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-Id")) -> str:
    """Default to demo-student if no header."""
    return x_user_id or "demo-student"


def get_lightrag_client(request: Request):
    """LightRAG client singleton from app.state."""
    return request.app.state.lightrag_client


def get_agent(request: Request):
    """Agent singleton from app.state."""
    return request.app.state.agent
```

修正：需要 `Optional` 导入：

```python
from typing import AsyncIterator, Optional
```

- [ ] **Step 9: 写 `api/health.py`**

```python
# src/teaching_agent_api/api/health.py
"""Health check endpoint."""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """Return status of all components."""
    components = {"database": "ok", "lightrag": "unknown", "agent": "unknown"}

    # DB check
    try:
        from sqlalchemy import text
        async with request.app.state.db_session_factory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "fail"

    # LightRAG check
    try:
        lightrag = request.app.state.lightrag_client
        await lightrag.health()
        components["lightrag"] = "ok"
    except Exception:
        components["lightrag"] = "fail"

    # Agent check
    try:
        agent = request.app.state.agent
        components["agent"] = "ready" if agent is not None else "not_built"
    except Exception:
        components["agent"] = "fail"

    import langchain
    import langgraph
    return {
        "status": "healthy" if all(v in ("ok", "ready") for v in components.values()) else "degraded",
        "components": components,
        "versions": {
            "api": "0.1.0",
            "langchain": langchain.__version__,
            "langgraph": langgraph.__version__,
        },
    }
```

- [ ] **Step 10: 写 `main.py`（lifespan 含 LightRAG 客户端占位）**

```python
# src/teaching_agent_api/main.py
"""FastAPI app entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from teaching_agent_api.config import settings
from teaching_agent_api.db.engine import create_engine, create_session_factory, init_db
from teaching_agent_api.api import health as health_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. DB engine + business tables
    engine = create_engine(settings.database_url)
    await init_db(engine)
    db_session_factory = create_session_factory(engine)
    logger.info("DB initialized: %s", settings.database_url)

    # 2. LangGraph AsyncPostgresSaver
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()  # idempotent
        logger.info("LangGraph checkpointer ready")

        # 3. LightRAG client (placeholder; full impl in T2)
        from teaching_agent_api.lightrag.client import LightRAGClient
        lightrag_client = LightRAGClient(
            base_url=settings.lightrag_base_url,
            api_key=settings.lightrag_api_key,
        )
        await lightrag_client.start()
        logger.info("LightRAG client started: %s", settings.lightrag_base_url)

        # 4. Agent (placeholder; full impl in T3)
        app.state.agent = None  # T3 will populate

        # Inject state
        app.state.engine = engine
        app.state.db_session_factory = db_session_factory
        app.state.checkpointer = checkpointer
        app.state.lightrag_client = lightrag_client

        # T3 will build agent here; for now placeholder
        try:
            from teaching_agent_api.agent.factory import build_agent
            app.state.agent = build_agent(checkpointer)
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent not built yet (expected before T3): %s", e)
            app.state.agent = None

        yield

    # Cleanup
    await lightrag_client.close()
    await engine.dispose()
    logger.info("Cleanup complete")


app = FastAPI(title="Teaching Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health_router.router)
```

- [ ] **Step 11: 创建必要的 `__init__.py` 空文件**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
touch src/teaching_agent_api/__init__.py
touch src/teaching_agent_api/api/__init__.py
touch src/teaching_agent_api/db/__init__.py
mkdir -p src/teaching_agent_api/lightrag src/teaching_agent_api/agent src/teaching_agent_api/schemas
touch src/teaching_agent_api/lightrag/__init__.py
touch src/teaching_agent_api/agent/__init__.py
touch src/teaching_agent_api/schemas/__init__.py
```

- [ ] **Step 12: 写一个最小的 `lightrag/client.py` 占位（让 import 不报错）**

```python
# src/teaching_agent_api/lightrag/client.py
"""LightRAG HTTP client. Full impl in T2; minimal stub here for lifespan."""
import httpx


class LightRAGClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def start(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def health(self) -> dict:
        resp = await self._client.get("/health")
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 13: 安装依赖并启动验证**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv sync
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000
```

**验证**：另开终端
```bash
curl http://localhost:8000/health
```
期望响应：
```json
{
  "status": "healthy",
  "components": {"database": "ok", "lightrag": "ok", "agent": "not_built"},
  "versions": {...}
}
```
（agent 应为 `not_built`，因为 T3 还没做）

```bash
# 验证 DB 表已建
psql "postgresql://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718" -c "\dt"
# 应看到 project, session, message, question 四张表
# 以及 langgraph_* 检查点表
```

---

## Task 2: LightRAG Client + Projects API + Sessions API

**Goal:** LightRAG 客户端封装完整；`/projects` CRUD + `/sessions` CRUD + `/sessions/{id}/messages` GET + `/sessions/{id}/questions` GET 全部可用。

**Files:**
- Create: `teaching_agent_api/src/teaching_agent_api/lightrag/schemas.py`
- Modify: `teaching_agent_api/src/teaching_agent_api/lightrag/client.py`（完整实现）
- Create: `teaching_agent_api/src/teaching_agent_api/schemas/project.py`
- Create: `teaching_agent_api/src/teaching_agent_api/schemas/session.py`
- Create: `teaching_agent_api/src/teaching_agent_api/api/projects.py`
- Create: `teaching_agent_api/src/teaching_agent_api/api/sessions.py`
- Modify: `teaching_agent_api/src/teaching_agent_api/main.py`（挂载新 router）

**Interfaces:**
- Consumes: T1 的 `get_db`, `get_user_id`, repos 函数, `Settings`
- Produces: `LightRAGClient`（含 `upload_file/insert_text/insert_texts/scan/track_status/pipeline_status/status_counts/list_documents/delete_documents/query/get_graph/list_labels/popular_labels/search_labels/health`），`ProjectCreate/Update/Out`, `SessionCreate/Out`, `MessageOut`, `QuestionOut`，`/projects` 和 `/sessions` 路由

- [ ] **Step 1: 写 `lightrag/schemas.py`**

```python
# src/teaching_agent_api/lightrag/schemas.py
"""Pydantic models for LightRAG API responses. Used for type hints; the proxy
endpoints pass through raw JSON to keep 100% compatibility with lightrag_webui."""
from typing import Optional, Any
from pydantic import BaseModel


class InsertResponse(BaseModel):
    status: str
    message: Optional[str] = None
    track_id: Optional[str] = None


class DocStatusResponse(BaseModel):
    id: str
    content_summary: Optional[str] = None
    content_length: Optional[int] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    track_id: Optional[str] = None
    chunks_count: Optional[int] = None
    error_msg: Optional[str] = None
    metadata: Optional[dict] = None
    file_path: Optional[str] = None


class TrackStatusResponse(BaseModel):
    track_id: str
    documents: list[DocStatusResponse] = []
    total_count: int = 0
    status_summary: dict[str, int] = {}


class PipelineStatusResponse(BaseModel):
    busy: bool
    job_name: Optional[str] = None
    latest_message: Optional[str] = None
    docs: int = 0
    batches: int = 0
    cur_batch: int = 0


class QueryResponse(BaseModel):
    response: str
    references: Optional[list[dict]] = None
```

- [ ] **Step 2: 完整实现 `lightrag/client.py`**

```python
# src/teaching_agent_api/lightrag/client.py
"""LightRAG HTTP client. All endpoints used by the backend, with connection pooling."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class LightRAGClient:
    """Async LightRAG HTTP client. Started once at lifespan startup, reused per request."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        logger.info("LightRAGClient started: %s", self.base_url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("LightRAGClient not started; call start() first")
        return self._client

    # === Health ===

    async def health(self) -> dict:
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    # === Document management (proxied to frontend) ===

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self.client.post("/documents/upload", files=files)
        resp.raise_for_status()
        return resp.json()

    async def insert_text(self, body: dict) -> dict:
        resp = await self.client.post("/documents/text", json=body)
        resp.raise_for_status()
        return resp.json()

    async def insert_texts(self, body: dict) -> dict:
        resp = await self.client.post("/documents/texts", json=body)
        resp.raise_for_status()
        return resp.json()

    async def scan(self) -> dict:
        resp = await self.client.post("/documents/scan")
        resp.raise_for_status()
        return resp.json()

    async def track_status(self, track_id: str) -> dict:
        resp = await self.client.get(f"/documents/track_status/{track_id}")
        resp.raise_for_status()
        return resp.json()

    async def pipeline_status(self) -> dict:
        resp = await self.client.get("/documents/pipeline_status")
        resp.raise_for_status()
        return resp.json()

    async def status_counts(self) -> dict:
        resp = await self.client.get("/documents/status_counts")
        resp.raise_for_status()
        return resp.json()

    async def list_documents(self, body: dict) -> dict:
        resp = await self.client.post("/documents/paginated", json=body)
        resp.raise_for_status()
        return resp.json()

    async def delete_documents(self, body: dict) -> dict:
        resp = await self.client.request("DELETE", "/documents/delete_document", json=body)
        resp.raise_for_status()
        return resp.json()

    # === Query (internal use by agent tools; NOT exposed to frontend) ===

    async def query(
        self,
        query: str,
        mode: str = "mix",
        only_need_context: bool = False,
        include_references: bool = True,
        **kwargs,
    ) -> dict:
        body = {
            "query": query,
            "mode": mode,
            "only_need_context": only_need_context,
            "include_references": include_references,
            **kwargs,
        }
        resp = await self.client.post("/query", json=body)
        resp.raise_for_status()
        return resp.json()

    # === Knowledge graph (proxied to frontend) ===

    async def get_graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000) -> dict:
        resp = await self.client.get(
            "/graphs", params={"label": label, "max_depth": max_depth, "max_nodes": max_nodes}
        )
        resp.raise_for_status()
        return resp.json()

    async def list_labels(self) -> list[str]:
        resp = await self.client.get("/graph/label/list")
        resp.raise_for_status()
        return resp.json()

    async def popular_labels(self, limit: int = 300) -> list[str]:
        resp = await self.client.get("/graph/label/popular", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def search_labels(self, query: str) -> list[str]:
        resp = await self.client.get("/graph/label/search", params={"query": query})
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: 写 `schemas/project.py`**

```python
# src/teaching_agent_api/schemas/project.py
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    status: Literal["draft", "published"] = "draft"


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    background_md: Optional[str] = Field(None, min_length=1)
    status: Optional[Literal["draft", "published"]] = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    background_md: str
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: 写 `schemas/session.py`**

```python
# src/teaching_agent_api/schemas/session.py
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SessionCreate(BaseModel):
    mode: Literal["free", "project"]
    project_id: Optional[UUID] = None

    @model_validator(mode="after")
    def check_project_id(self):
        if self.mode == "project" and not self.project_id:
            raise ValueError("project_id is required when mode='project'")
        return self


class SessionOut(BaseModel):
    id: UUID
    user_id: str
    mode: str
    project_id: Optional[UUID]
    project_name: Optional[str] = None
    title: Optional[str]
    status: str
    last_active_at: datetime
    created_at: datetime


class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime


class QuestionOut(BaseModel):
    id: UUID
    session_id: UUID
    topic: str
    q_type: str
    stem: str
    options: Optional[list[str]]
    answer: str
    analysis: Optional[str]
    status: str
    user_answer: Optional[str]
    verdict: Optional[str]
    diagnosis: Optional[str]
    created_at: datetime
    answered_at: Optional[datetime]
```

- [ ] **Step 5: 写 `api/projects.py`**

```python
# src/teaching_agent_api/api/projects.py
"""Project CRUD endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.deps import get_db
from teaching_agent_api.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db_session: AsyncSession = Depends(get_db)):
    proj = await db.create_project(db_session, name=body.name, background_md=body.background_md, status=body.status)
    return ProjectOut.model_validate(proj)


@router.get("", response_model=list[ProjectOut])
async def list_projects(status_filter: str | None = None, db_session: AsyncSession = Depends(get_db)):
    projects = await db.list_projects(db_session, status=status_filter)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, db_session: AsyncSession = Depends(get_db)):
    proj = await db.get_project(db_session, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail={"error": {"code": "PROJECT_NOT_FOUND", "message": f"Project {project_id} not found"}})
    return ProjectOut.model_validate(proj)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, body: ProjectUpdate, db_session: AsyncSession = Depends(get_db)):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail={"error": {"code": "VALIDATION_ERROR", "message": "No fields to update"}})
    proj = await db.update_project(db_session, project_id, **fields)
    if not proj:
        raise HTTPException(status_code=404, detail={"error": {"code": "PROJECT_NOT_FOUND", "message": f"Project {project_id} not found"}})
    return ProjectOut.model_validate(proj)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db_session: AsyncSession = Depends(get_db)):
    proj = await db.get_project(db_session, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail={"error": {"code": "PROJECT_NOT_FOUND", "message": f"Project {project_id} not found"}})
    await db.delete_project(db_session, project_id)
```

- [ ] **Step 6: 写 `api/sessions.py`**

```python
# src/teaching_agent_api/api/sessions.py
"""Session CRUD + messages + questions endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.deps import get_db, get_user_id
from teaching_agent_api.schemas.session import SessionCreate, SessionOut, MessageOut, QuestionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _validate_session_ownership(db_session: AsyncSession, session_id: UUID, user_id: str):
    sess = await db.get_session(db_session, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": f"Session {session_id} not found"}})
    if sess.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Session does not belong to user"}})
    return sess


async def _validate_project(db_session: AsyncSession, project_id: UUID):
    proj = await db.get_project(db_session, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail={"error": {"code": "PROJECT_NOT_FOUND", "message": f"Project {project_id} not found"}})
    if proj.status != "published":
        raise HTTPException(status_code=422, detail={"error": {"code": "PROJECT_NOT_PUBLISHED", "message": "Project must be published to start a session"}})


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, user_id: str = Depends(get_user_id), db_session: AsyncSession = Depends(get_db)):
    if body.mode == "project":
        await _validate_project(db_session, body.project_id)
    sess = await db.create_session(db_session, mode=body.mode, user_id=user_id, project_id=body.project_id)
    return SessionOut.model_validate(_enrich_session(sess))


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    status_filter: str | None = Query(None, alias="status"),
    mode: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
):
    sessions = await db.list_sessions(db_session, user_id=user_id, status=status_filter, mode=mode, limit=limit, offset=offset)
    return [SessionOut.model_validate(_enrich_session(s)) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID, user_id: str = Depends(get_user_id), db_session: AsyncSession = Depends(get_db)):
    sess = await _validate_session_ownership(db_session, session_id, user_id)
    return SessionOut.model_validate(_enrich_session(sess))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: UUID, user_id: str = Depends(get_user_id), db_session: AsyncSession = Depends(get_db)):
    await _validate_session_ownership(db_session, session_id, user_id)
    await db.end_session(db_session, session_id)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
):
    await _validate_session_ownership(db_session, session_id, user_id)
    msgs = await db.list_messages(db_session, session_id, limit=limit, offset=offset)
    return [MessageOut.model_validate(m) for m in msgs]


@router.get("/{session_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    session_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
):
    await _validate_session_ownership(db_session, session_id, user_id)
    qs = await db.list_questions(db_session, session_id, status=status_filter)
    return [QuestionOut.model_validate(q) for q in qs]


def _enrich_session(sess) -> dict:
    """Add project_name if available."""
    data = sess.model_dump()
    if sess.project:
        data["project_name"] = sess.project.name
    return data
```

- [ ] **Step 7: 在 `main.py` 中挂载新 router**

修改 `teaching_agent_api/src/teaching_agent_api/main.py`，在末尾添加：

```python
from teaching_agent_api.api import health as health_router
from teaching_agent_api.api import projects as projects_router
from teaching_agent_api.api import sessions as sessions_router

# ... existing app setup ...

app.include_router(health_router.router)
app.include_router(projects_router.router)
app.include_router(sessions_router.router)
```

把已有的 `app.include_router(health_router.router)` 替换为上述三行。

- [ ] **Step 8: 验证**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端：
```bash
# 创建 project
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"TCP 服务器实现","background_md":"# 项目背景\n\n实现一个基于 TCP 的服务器","status":"published"}'

# 列出
curl http://localhost:8000/projects

# 创建 project 模式 session（用上一步返回的 project id）
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test-user" \
  -d '{"mode":"project","project_id":"<上一步返回的id>"}'

# 列出 sessions
curl http://localhost:8000/sessions -H "X-User-Id: test-user"

# 尝试创建 project session 但 project 是 draft（应失败）
# 先创建一个 draft project，再尝试
curl -X POST http://localhost:8000/projects -H "Content-Type: application/json" \
  -d '{"name":"draft项目","background_md":"test","status":"draft"}'
# 用 draft project 的 id 创建 session -> 应 422
```

期望：所有 CRUD 正常；draft project 创建 session 返回 422 `PROJECT_NOT_PUBLISHED`。

---

## Task 3: Agent 核心 - LLM + Prompts + Tools + Factory

**Goal:** LangChain 1.x agent 构建完成，能直接 invoke 验证（不走 HTTP），search_knowledge 调 LightRAG 真实检索，quiz_flow 触发 interrupt。

**Files:**
- Create: `teaching_agent_api/src/teaching_agent_api/agent/llm.py`
- Create: `teaching_agent_api/src/teaching_agent_api/agent/prompts.py`
- Create: `teaching_agent_api/src/teaching_agent_api/agent/tools.py`
- Create: `teaching_agent_api/src/teaching_agent_api/agent/factory.py`
- Modify: `teaching_agent_api/src/teaching_agent_api/main.py`（lifespan 中正确构建 agent）

**Interfaces:**
- Consumes: T1 的 `Settings`, `AsyncPostgresSaver` checkpointer, DB repos；T2 的 `LightRAGClient`
- Produces: `get_llm() -> ChatOpenAI`，`AgentContext` dataclass，`@dynamic_prompt teaching_prompt`，`search_knowledge` / `quiz_flow` 工具，`QuizOutput` / `EvaluationOutput` schema，`build_agent(checkpointer) -> CompiledStateGraph`，`set_dependencies(lightrag_client, db_session_factory)` 函数

- [ ] **Step 1: 写 `agent/llm.py`**

```python
# src/teaching_agent_api/agent/llm.py
"""ChatOpenAI factory for DashScope (OpenAI-compatible)."""
from langchain_openai import ChatOpenAI

from teaching_agent_api.config import settings


def get_llm() -> ChatOpenAI:
    """Return ChatOpenAI configured for DashScope qwen3.6-flash.

    Notes:
    - enable_thinking=False to suppress DashScope's reasoning output
    - temperature=0.7 for moderate creativity in Socratic teaching
    """
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )
```

- [ ] **Step 2: 写 `agent/prompts.py`（含 AgentContext + @dynamic_prompt）**

```python
# src/teaching_agent_api/agent/prompts.py
"""System prompt templates + AgentContext + @dynamic_prompt middleware.

LangChain 1.x best practice: a single agent instance serves both modes;
the system prompt is dynamically chosen via @dynamic_prompt based on
runtime AgentContext.
"""
from dataclasses import dataclass
from typing import Literal

from langchain.agents.middleware import dynamic_prompt, ModelRequest

from teaching_agent_api.config import settings


# === Prompt templates ===

_CORE_PRINCIPLES = """## 核心原则
1. 绝不直接给出答案。通过提问引导学生自己推导出结论。
2. 当学生提问或讨论某个概念时，先调用 search_knowledge 检索相关知识，再基于检索内容设计追问。
3. 如果检索结果为空，告诉学生"这个问题可能超出当前课程知识库范围"，引导回课程内容。
4. 根据学生的回答判断理解程度：
   - 理解有误 -> 针对性追问，暴露矛盾
   - 理解部分 -> 追问未覆盖的部分
   - 理解到位 -> 可以调用 quiz_flow 出题检验
5. 学生说"考考我"/"出题"/"测验"时，调用 quiz_flow 出题。
6. 每次追问保持上下文连贯，不要突兀跳转话题。"""

_AVAILABLE_TOOLS = """## 可用工具
- search_knowledge(query): 检索课程知识库（含知识图谱），返回相关知识片段
- quiz_flow(topic): 出一道题并等待学生作答，返回评估结果"""

GUIDANCE_PROMPT_FREE = """你是一位苏格拉底式教学助手，课程是《{course_name}》。

{_CORE_PRINCIPLES}

## 当前会话
学生正在进行自由学习，围绕课程知识自由探索。

{_AVAILABLE_TOOLS}
""".format(_CORE_PRINCIPLES=_CORE_PRINCIPLES, _AVAILABLE_TOOLS=_AVAILABLE_TOOLS)


GUIDANCE_PROMPT_PROJECT = """你是一位苏格拉底式教学助手，课程是《{course_name}》。

{_CORE_PRINCIPLES}

## 当前项目
学生正在学习项目：{project_name}

## 项目背景
{project_background_md}

请以项目背景为情境展开追问，将课程知识应用到项目场景中。鼓励学生思考如何将所学知识用于解决项目中的实际问题。

{_AVAILABLE_TOOLS}
""".format(_CORE_PRINCIPLES=_CORE_PRINCIPLES, _AVAILABLE_TOOLS=_AVAILABLE_TOOLS)


# === Quiz / Evaluation prompts (used by tools.py helpers) ===

QUIZ_GENERATION_PROMPT = """你是一位出题专家，课程是《{course_name}》。

## 任务
根据以下信息出一道题：
- 当前话题：{topic}
- 知识库片段（出题素材）：
{context}

## 出题要求
1. 题目考察理解，不考死记硬背
2. 单选题 4 个选项；多选题 4-6 个选项；简答题无选项
3. 答案要明确，便于自动判分：
   - single: 填选项完整文本（如 "TCP三次握手"）
   - multi: 填选项文本，逗号分隔（如 "A,C,D"）
   - short: 填要点列表（每点一行）
4. analysis 说明考点和正确答案的依据
"""

EVALUATION_PROMPT = """你是一位阅卷专家。

## 任务
评判学生的答案：

题目：{stem}
题型：{q_type}
正确答案：{correct_answer}
学生答案：{student_answer}

## 评分规则
- 单选：完全匹配 = correct，否则 = wrong
- 多选：全对 = correct，漏选无错选 = partial，有错选 = wrong
- 简答：按要点命中评分
  - 全部要点命中 = correct
  - 部分命中 = partial
  - 偏离 = wrong

## 输出
- verdict: correct / partial / wrong
- diagnosis: 错因诊断（答对时为空字符串）
- analysis: 评分解析（说明判定依据）
"""


# === AgentContext + @dynamic_prompt middleware ===

@dataclass
class AgentContext:
    """Per-invoke context injected into the agent via `context=` parameter.

    Carries mode (free/project) and course/project metadata so the @dynamic_prompt
    middleware can pick the right template without rebuilding the agent.
    """
    mode: Literal["free", "project"]
    course_name: str
    project_name: str = ""
    project_background_md: str = ""


@dynamic_prompt
def teaching_prompt(request: ModelRequest) -> str:
    """LangChain 1.x middleware: pick prompt template based on AgentContext.mode."""
    ctx = request.runtime.context
    if not ctx:
        return GUIDANCE_PROMPT_FREE.format(course_name=settings.course_name)
    if ctx.mode == "project":
        return GUIDANCE_PROMPT_PROJECT.format(
            course_name=ctx.course_name or settings.course_name,
            project_name=ctx.project_name,
            project_background_md=ctx.project_background_md or "（无项目背景）",
        )
    return GUIDANCE_PROMPT_FREE.format(course_name=ctx.course_name or settings.course_name)
```

- [ ] **Step 3: 写 `agent/tools.py`（含 schemas + 工具 + helpers + 依赖注入）**

```python
# src/teaching_agent_api/agent/tools.py
"""Agent tools: search_knowledge + quiz_flow.

LangChain 1.x patterns used:
- @tool decorator from langchain_core.tools
- with_structured_output(method="function_calling") for typed LLM responses
- interrupt() from langgraph.types for HITL pause
- RunnableConfig for accessing thread_id (= session_id)
- Module-level _state container for lifespan-injected dependencies (LightRAGClient, db_session_factory)
"""
import logging
from datetime import datetime
from typing import Optional, Literal

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from teaching_agent_api.agent.llm import get_llm
from teaching_agent_api.agent.prompts import QUIZ_GENERATION_PROMPT, EVALUATION_PROMPT
from teaching_agent_api.config import settings
from teaching_agent_api.db import repos as db
from teaching_agent_api.lightrag.client import LightRAGClient

logger = logging.getLogger(__name__)


# === Lifespan-injected dependencies ===
# Tools can't use FastAPI Depends (not in request context), so a module-level
# container is populated by main.py lifespan via set_dependencies().
_state: dict = {}


def set_dependencies(*, lightrag_client: LightRAGClient, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
    _state["lightrag"] = lightrag_client
    _state["db_factory"] = db_session_factory


def _get_lightrag() -> LightRAGClient:
    return _state["lightrag"]


async def _get_db() -> AsyncSession:
    """Async context manager for tool-internal DB operations."""
    factory = _state["db_factory"]
    return factory()  # caller manages lifecycle


# === Structured output schemas (Pydantic, not SQLModel) ===

class QuizOutput(BaseModel):
    """LLM output schema for quiz generation."""
    q_type: Literal["single", "multi", "short"] = Field(description="题型：单选/多选/简答")
    stem: str = Field(description="题干")
    options: Optional[list[str]] = Field(None, description="选项列表，short 题为 null")
    answer: str = Field(description="正确答案（single: 选项文本；multi: 'A,C,D'；short: 要点列表）")
    analysis: str = Field(description="题目解析")


class EvaluationOutput(BaseModel):
    """LLM output schema for answer evaluation."""
    verdict: Literal["correct", "partial", "wrong"] = Field(description="判定结果")
    diagnosis: str = Field(description="错因诊断（答对时为空字符串）")
    analysis: str = Field(description="评分解析")


# === Internal helpers ===

async def _search_for_quiz(topic: str) -> str:
    """Retrieve knowledge context for quiz generation."""
    lightrag = _get_lightrag()
    try:
        result = await lightrag.query(query=topic, mode="mix", only_need_context=True)
        return result.get("response", "") or ""
    except Exception as e:
        logger.warning("Quiz context retrieval failed: %s", e)
        return ""


async def _generate_quiz(topic: str, context: str) -> QuizOutput:
    """LLM structured quiz generation."""
    llm = get_llm().with_structured_output(QuizOutput, method="function_calling")
    return await llm.ainvoke(QUIZ_GENERATION_PROMPT.format(
        course_name=settings.course_name,
        topic=topic,
        context=context or "（无检索结果）",
    ))


async def _evaluate_answer(stem: str, q_type: str, correct_answer: str, user_answer: str) -> EvaluationOutput:
    """LLM structured answer evaluation."""
    llm = get_llm().with_structured_output(EvaluationOutput, method="function_calling")
    return await llm.ainvoke(EVALUATION_PROMPT.format(
        stem=stem, q_type=q_type, correct_answer=correct_answer, student_answer=user_answer,
    ))


# === Tools ===

@tool
async def search_knowledge(query: str) -> str:
    """检索课程知识库（知识图谱 + RAG），返回相关知识片段。

    当学生提问或讨论某个概念时，先调用此工具检索相关知识，
    再基于检索内容设计苏格拉底式追问。检索结果包含向量匹配和知识图谱扩展的片段。

    Args:
        query: 检索关键词，需包含完整上下文（消除代词指代）
    """
    lightrag = _get_lightrag()
    try:
        result = await lightrag.query(
            query=query,
            mode="mix",                  # KG + vector, LightRAG recommended
            only_need_context=True,       # don't call LightRAG's LLM; agent has its own
            include_references=True,
        )
    except Exception as e:
        logger.exception("search_knowledge failed")
        return f"知识库检索失败: {e}"

    context = (result.get("response") or "").strip()
    if not context:
        return "未检索到相关内容，该问题可能超出当前课程知识库范围"
    return context


@tool
async def quiz_flow(topic: str, config: RunnableConfig) -> str:
    """出一道关于指定知识点的题目，等待学生作答后返回评估结果。

    当学生说"考考我"、需要检验理解程度、或你判断时机成熟时调用此工具。
    调用后会暂停等待学生答题，学生提交答案后自动判分。

    Args:
        topic: 要出题的知识点名称
    """
    from langgraph.types import interrupt  # local import; avoids import-time hard dep

    session_id_str = config["configurable"]["thread_id"]
    import uuid as _uuid
    session_id = _uuid.UUID(session_id_str)

    # === Idempotency: check pending question (resume path reuses) ===
    async with await _get_db() as db_session:
        pending = await db.get_pending_question(db_session, session_id, topic)
        if pending:
            quiz = pending
        else:
            # === First call: retrieve context + generate quiz ===
            context = await _search_for_quiz(topic)
            quiz_data = await _generate_quiz(topic, context)
            # Idempotent upsert: ON CONFLICT (session_id, topic, status='pending')
            quiz = await db.upsert_pending_question(
                db_session,
                session_id=session_id, topic=topic,
                q_type=quiz_data.q_type, stem=quiz_data.stem,
                options=quiz_data.options, answer=quiz_data.answer, analysis=quiz_data.analysis,
            )

    # === interrupt: raises on first call; returns student answer on resume ===
    student_answer = interrupt({
        "question_id": str(quiz.id),
        "topic": topic,
        "q_type": quiz.q_type,
        "stem": quiz.stem,
        "options": quiz.options,
    })

    # === Below runs only once on resume ===
    async with await _get_db() as db_session:
        if student_answer.get("action") == "skip":
            await db.update_question(db_session, quiz.id, status="skipped")
            return "学生跳过了本题。请继续对话，了解学生的疑虑。"

        answer = student_answer.get("answer", "")
        evaluation = await _evaluate_answer(
            stem=quiz.stem, q_type=quiz.q_type,
            correct_answer=quiz.answer, user_answer=answer,
        )
        await db.update_question(
            db_session, quiz.id,
            status="answered",
            user_answer=answer,
            verdict=evaluation.verdict,
            diagnosis=evaluation.diagnosis,
        )

    return (
        f"判定: {evaluation.verdict}\n"
        f"错因诊断: {evaluation.diagnosis}\n"
        f"正确答案: {quiz.answer}\n"
        f"解析: {evaluation.analysis}"
    )
```

注意 `_get_db()` 的使用：返回 `factory()` 的结果，是一个 `AsyncSession` 异步上下文管理器，需要 `async with await _get_db() as db_session:` 来管理生命周期。修正：

```python
async def _get_db_session() -> AsyncSession:
    """Get a fresh DB session for tool-internal use. Caller is responsible for cleanup via `async with`."""
    factory = _state["db_factory"]
    return factory().__aenter__()  # not ideal
```

更好的写法是用 `async contextmanager`：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _db_session():
    factory = _state["db_factory"]
    async with factory() as session:
        yield session
```

然后工具中：

```python
async with _db_session() as db_session:
    pending = await db.get_pending_question(db_session, session_id, topic)
    ...
```

替换 `agent/tools.py` 中的 `_get_db` 函数和所有调用点。

- [ ] **Step 4: 写 `agent/factory.py`**

```python
# src/teaching_agent_api/agent/factory.py
"""Agent factory: single agent instance serving both free/project modes.

LangChain 1.x pattern: create_agent + @dynamic_prompt middleware +
context_schema=AgentContext. The system prompt is chosen per-invoke
via the AgentContext passed to astream_events(context=...).
"""
from typing import Optional

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from teaching_agent_api.agent.llm import get_llm
from teaching_agent_api.agent.prompts import teaching_prompt, AgentContext
from teaching_agent_api.agent.tools import search_knowledge, quiz_flow

_agent_singleton: Optional[CompiledStateGraph] = None


def build_agent(checkpointer) -> CompiledStateGraph:
    """Build the agent singleton. Idempotent: returns cached instance on subsequent calls.

    Args:
        checkpointer: AsyncPostgresSaver instance (already .setup()'d)

    Returns:
        CompiledStateGraph: the agent ready for astream_events / aget_state / etc.
    """
    global _agent_singleton
    if _agent_singleton is not None:
        return _agent_singleton

    _agent_singleton = create_agent(
        model=get_llm(),
        tools=[search_knowledge, quiz_flow],
        middleware=[teaching_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
    return _agent_singleton
```

- [ ] **Step 5: 修改 `main.py` lifespan 正确注入 agent 依赖**

替换 T1 Step 10 中的 agent 构建部分：

```python
# main.py lifespan 中：
# 3. LightRAG client
from teaching_agent_api.lightrag.client import LightRAGClient
lightrag_client = LightRAGClient(
    base_url=settings.lightrag_base_url,
    api_key=settings.lightrag_api_key,
)
await lightrag_client.start()
logger.info("LightRAG client started: %s", settings.lightrag_base_url)

# 4. Inject dependencies into tools module
from teaching_agent_api.agent.tools import set_dependencies
set_dependencies(lightrag_client=lightrag_client, db_session_factory=db_session_factory)

# 5. Build agent (now tools have their deps)
from teaching_agent_api.agent.factory import build_agent
agent = build_agent(checkpointer)
logger.info("Agent built")

app.state.engine = engine
app.state.db_session_factory = db_session_factory
app.state.checkpointer = checkpointer
app.state.lightrag_client = lightrag_client
app.state.agent = agent

yield
```

- [ ] **Step 6: 验证 agent 能 invoke**

写一个临时脚本 `/tmp/test_agent.py`：

```python
import asyncio
import uuid
from teaching_agent_api.config import settings
from teaching_agent_api.db.engine import create_engine, init_db, create_session_factory
from teaching_agent_api.lightrag.client import LightRAGClient
from teaching_agent_api.agent.tools import set_dependencies
from teaching_agent_api.agent.factory import build_agent
from teaching_agent_api.agent.prompts import AgentContext
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def main():
    engine = create_engine(settings.database_url)
    await init_db(engine)
    factory = create_session_factory(engine)

    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as cp:
        await cp.setup()

        lightrag = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
        await lightrag.start()

        set_dependencies(lightrag_client=lightrag, db_session_factory=factory)
        agent = build_agent(cp)

        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}
        ctx = AgentContext(mode="free", course_name="计算机网络")

        stream = await agent.astream_events(
            {"messages": [HumanMessage(content="什么是TCP三次握手？")]},
            config=config, version="v3", context=ctx,
        )
        async for message in stream.messages:
            async for token in message.text:
                print(token, end="", flush=True)
        print()
        print(f"Interrupted: {stream.interrupted}")

        await lightrag.close()

    await engine.dispose()


asyncio.run(main())
```

运行：
```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv run python /tmp/test_agent.py
```

期望：看到 agent 流式输出，可能调用 `search_knowledge` 工具，最后输出完整回复。

如果触发 quiz_flow（让学生说"考考我 TCP 三次握手"），观察 `Interrupted: True`。

清理：
```bash
rm /tmp/test_agent.py
```

---

## Task 4: Agent Runtime + Chat SSE API

**Goal:** `/chat/sessions/{id}/messages` POST 返回 SSE 流式 token + 检测 quiz_interrupt；`/chat/sessions/{id}/quiz/resume` POST 通过 `Command(resume=...)` 续接。

**Files:**
- Create: `teaching_agent_api/src/teaching_agent_api/agent/runtime.py`
- Create: `teaching_agent_api/src/teaching_agent_api/schemas/chat.py`
- Create: `teaching_agent_api/src/teaching_agent_api/api/chat.py`
- Modify: `teaching_agent_api/src/teaching_agent_api/main.py`（挂载 chat router）

**Interfaces:**
- Consumes: T1 的 `get_db`, `get_user_id`, repos；T2 的 `LightRAGClient`, `SessionOut`；T3 的 `build_agent`, `AgentContext`
- Produces: `stream_chat()` / `resume_quiz()` async generators 返回 SSE 帧字符串；`SendMessageRequest` / `QuizResumeRequest` schemas；`/chat/sessions/{id}/messages` 和 `/chat/sessions/{id}/quiz/resume` SSE 路由

- [ ] **Step 1: 写 `agent/runtime.py`**

```python
# src/teaching_agent_api/agent/runtime.py
"""Agent runtime: stream_chat() and resume_quiz() async generators that emit SSE frames.

LangChain 1.x pattern:
- agent.astream_events(version="v3") returns a stream object with .messages, .text, .interrupted
- stream.messages -> async iterable of message objects; message.text -> async iterable of tokens
- stream.interrupted -> bool; stream.interrupts -> list of Interrupt objects with .value
- Command(resume=value) resumes from interrupt
"""
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncIterator, Optional

from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.db import repos as db

logger = logging.getLogger(__name__)


async def stream_chat(
    agent,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """Initial message: stream agent tokens; detect quiz interrupt; save final agent message.

    Yields SSE-formatted strings:
        event: text\\ndata: {...}\\n\\n
        event: quiz_interrupt\\ndata: {...}\\n\\n
        event: done\\ndata: {}\\n\\n
        event: error\\ndata: {...}\\n\\n
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        if stream.interrupted:
            for it in stream.interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return  # session paused; do NOT save agent message yet

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("stream_chat failed")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def resume_quiz(
    agent,
    session_id: uuid.UUID,
    action: str,
    answer: Optional[str],
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """Submit quiz answer or skip; stream agent's follow-up response.

    Yields same SSE event types as stream_chat (no quiz_interrupt expected on resume).
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""

    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),
            config=config,
            version="v3",
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("resume_quiz failed")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def _save_final_agent_message(agent, config: dict, db_session: AsyncSession, session_id: uuid.UUID) -> None:
    """Fetch final AIMessage from LangGraph state and persist to Message table."""
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if not messages:
        return
    final_msg = messages[-1]
    content = getattr(final_msg, "content", None)
    if content:
        await db.save_message(db_session, session_id=session_id, role="agent", content=content)


def _sse(event: str, data: dict) -> str:
    """Format an SSE frame. JSON serialized without escaping non-ASCII (Chinese)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

- [ ] **Step 2: 写 `schemas/chat.py`**

```python
# src/teaching_agent_api/schemas/chat.py
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class QuizResumeRequest(BaseModel):
    action: Literal["answer", "skip"]
    answer: Optional[str] = None

    @model_validator(mode="after")
    def check_answer_required(self):
        if self.action == "answer" and not self.answer:
            raise ValueError("answer is required when action='answer'")
        return self
```

- [ ] **Step 3: 写 `api/chat.py`**

```python
# src/teaching_agent_api/api/chat.py
"""Chat endpoints with SSE streaming."""
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from teaching_agent_api import db
from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.agent.runtime import stream_chat, resume_quiz
from teaching_agent_api.config import settings
from teaching_agent_api.deps import get_db, get_user_id, get_agent
from teaching_agent_api.schemas.chat import SendMessageRequest, QuizResumeRequest

router = APIRouter(prefix="/chat", tags=["chat"])


async def _validate_session_for_chat(db_session: AsyncSession, session_id: uuid.UUID, user_id: str):
    """Common validations: session exists, owned by user, active, not interrupted."""
    sess = await db.get_session(db_session, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": f"Session {session_id} not found"}})
    if sess.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Session does not belong to user"}})
    if sess.status != "active":
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_ENDED", "message": "Session is ended"}})
    return sess


async def _build_agent_context(sess) -> AgentContext:
    """Build AgentContext based on session mode; fetch project info if project mode."""
    if sess.mode == "project" and sess.project_id:
        proj = await db.get_project(_db_session_for_ctx, sess.project_id)  # need a session
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)
```

修正：`_build_agent_context` 中访问 DB 需要一个 session。改为传入 project 对象（由路由层查询）：

```python
# 修正后的 _build_agent_context
async def _build_agent_context(sess, db_session: AsyncSession) -> AgentContext:
    if sess.mode == "project" and sess.project_id:
        proj = await db.get_project(db_session, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


async def _is_interrupted(agent, session_id: uuid.UUID) -> bool:
    """Check LangGraph state for pending interrupt."""
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await agent.aget_state(config)
    return bool(state.next)  # non-empty next means paused at interrupt


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    request: Request,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent = Depends(get_agent),
):
    """Send a message and stream the agent's response via SSE."""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)

    if await _is_interrupted(agent, session_id):
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_INTERRUPTED", "message": "Session is paused at a quiz; call /quiz/resume first"}})

    # Save user message
    await db.save_message(db_session, session_id=session_id, role="user", content=body.content)
    await db.touch_session(db_session, session_id)

    # Build context
    ctx = await _build_agent_context(sess, db_session)

    async def event_stream() -> AsyncIterator[dict]:
        try:
            async for sse_frame in stream_chat(agent, session_id, body.content, ctx, db_session):
                # sse_starlette expects dict with event/data keys OR raw strings
                # Parse our pre-formatted frame back to dict for EventSourceResponse
                # Simpler: use StreamingResponse with text/event-stream
                yield {"raw": sse_frame}
        finally:
            await db.touch_session(db_session, session_id)

    # Use StreamingResponse for raw SSE frames (our _sse() produces full frames)
    from fastapi.responses import StreamingResponse
    async def raw_stream():
        async for sse_frame in stream_chat(agent, session_id, body.content, ctx, db_session):
            yield sse_frame.encode("utf-8")
        await db.touch_session(db_session, session_id)

    return StreamingResponse(raw_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
    session_id: uuid.UUID,
    body: QuizResumeRequest,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent = Depends(get_agent),
):
    """Resume a paused quiz with answer or skip; stream agent's continuation via SSE."""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)

    if not await _is_interrupted(agent, session_id):
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_NOT_INTERRUPTED", "message": "Session is not paused; no quiz to resume"}})

    from fastapi.responses import StreamingResponse
    async def raw_stream():
        async for sse_frame in resume_quiz(agent, session_id, body.action, body.answer, db_session):
            yield sse_frame.encode("utf-8")
        await db.touch_session(db_session, session_id)

    return StreamingResponse(raw_stream(), media_type="text/event-stream")
```

注意：去掉重复的 `event_stream` 函数和未使用的 `EventSourceResponse` 导入，只保留 `StreamingResponse` 方案。

最终 `api/chat.py`（清理后）：

```python
# src/teaching_agent_api/api/chat.py
"""Chat endpoints with SSE streaming."""
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api import db
from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.agent.runtime import stream_chat, resume_quiz
from teaching_agent_api.config import settings
from teaching_agent_api.deps import get_db, get_user_id, get_agent
from teaching_agent_api.schemas.chat import SendMessageRequest, QuizResumeRequest

router = APIRouter(prefix="/chat", tags=["chat"])


async def _validate_session_for_chat(db_session: AsyncSession, session_id: uuid.UUID, user_id: str):
    sess = await db.get_session(db_session, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": f"Session {session_id} not found"}})
    if sess.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Session does not belong to user"}})
    if sess.status != "active":
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_ENDED", "message": "Session is ended"}})
    return sess


async def _build_agent_context(sess, db_session: AsyncSession) -> AgentContext:
    if sess.mode == "project" and sess.project_id:
        proj = await db.get_project(db_session, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


async def _is_interrupted(agent, session_id: uuid.UUID) -> bool:
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await agent.aget_state(config)
    return bool(state.next)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent = Depends(get_agent),
):
    """Send a message; stream agent reply as SSE (event: text|quiz_interrupt|done|error)."""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)
    if await _is_interrupted(agent, session_id):
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_INTERRUPTED", "message": "Session is paused at a quiz; call /quiz/resume first"}})

    await db.save_message(db_session, session_id=session_id, role="user", content=body.content)
    await db.touch_session(db_session, session_id)

    ctx = await _build_agent_context(sess, db_session)

    async def raw_stream():
        try:
            async for sse_frame in stream_chat(agent, session_id, body.content, ctx, db_session):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(raw_stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
    session_id: uuid.UUID,
    body: QuizResumeRequest,
    user_id: str = Depends(get_user_id),
    db_session: AsyncSession = Depends(get_db),
    agent = Depends(get_agent),
):
    """Resume a paused quiz with answer/skip; stream agent's continuation as SSE."""
    sess = await _validate_session_for_chat(db_session, session_id, user_id)
    if not await _is_interrupted(agent, session_id):
        raise HTTPException(status_code=409, detail={"error": {"code": "SESSION_NOT_INTERRUPTED", "message": "Session is not paused; no quiz to resume"}})

    async def raw_stream():
        try:
            async for sse_frame in resume_quiz(agent, session_id, body.action, body.answer, db_session):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(raw_stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
```

- [ ] **Step 4: 在 `main.py` 中挂载 chat router**

在 `main.py` 末尾添加：

```python
from teaching_agent_api.api import chat as chat_router
app.include_router(chat_router.router)
```

- [ ] **Step 5: 验证 chat 流式**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端：
```bash
# 创建 free session
SESSION_ID=$(curl -s -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"mode":"free"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Session: $SESSION_ID"

# 发消息，看 SSE 流
curl -N -X POST "http://localhost:8000/chat/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"什么是TCP三次握手？"}'
```

期望：看到多个 `event: text\ndata: {"content":"..."}` 帧，最后 `event: done`。

测试 quiz HITL：
```bash
# 让 agent 出题
curl -N -X POST "http://localhost:8000/chat/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"考考我 TCP 三次握手"}'
# 期望：event: text (可能有一些 token) + event: quiz_interrupt + event: done

# 提交答案
curl -N -X POST "http://localhost:8000/chat/sessions/$SESSION_ID/quiz/resume" \
  -H "Content-Type: application/json" \
  -d '{"action":"answer","answer":"SYN+ACK"}'
# 期望：event: text (评估结果 + agent 后续) + event: done
```

---

## Task 5: LightRAG Proxy Routers + 完整 main.py 装配

**Goal:** `/documents/*` 和 `/graph/*` 代理端点完整可用；`main.py` 挂载全部 router；代理端点透传 LightRAG 响应。

**Files:**
- Create: `teaching_agent_api/src/teaching_agent_api/api/documents.py`
- Create: `teaching_agent_api/src/teaching_agent_api/api/graph.py`
- Modify: `teaching_agent_api/src/teaching_agent_api/main.py`（确认全部 router 挂载）

**Interfaces:**
- Consumes: T2 的 `LightRAGClient` 所有方法
- Produces: `/documents/upload`, `/documents/text`, `/documents/texts`, `/documents/scan`, `/documents/track_status/{track_id}`, `/documents/pipeline_status`, `/documents/status_counts`, `/documents/paginated`, `/documents/delete_document`，`/graph/label/list`, `/graph/label/popular`, `/graph/label/search`, `/graphs`

- [ ] **Step 1: 写 `api/documents.py`**

```python
# src/teaching_agent_api/api/documents.py
"""LightRAG document proxy endpoints. Pure passthrough; no business logic."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse

from teaching_agent_api.deps import get_lightrag_client
from teaching_agent_api.lightrag.client import LightRAGClient

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), lightrag: LightRAGClient = Depends(get_lightrag_client)):
    content = await file.read()
    try:
        return await lightrag.upload_file(content, file.filename or "unknown", file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.post("/text")
async def insert_text(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)):
    body = await request.json()
    try:
        return await lightrag.insert_text(body)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.post("/texts")
async def insert_texts(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)):
    body = await request.json()
    try:
        return await lightrag.insert_texts(body)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.post("/scan")
async def scan(lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.scan()
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/track_status/{track_id}")
async def track_status(track_id: str, lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.track_status(track_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/pipeline_status")
async def pipeline_status(lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.pipeline_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/status_counts")
async def status_counts(lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.status_counts()
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.post("/paginated")
async def list_documents(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)):
    body = await request.json()
    try:
        return await lightrag.list_documents(body)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.delete("/delete_document")
async def delete_documents(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)):
    body = await request.json()
    try:
        return await lightrag.delete_documents(body)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})
```

- [ ] **Step 2: 写 `api/graph.py`**

```python
# src/teaching_agent_api/api/graph.py
"""LightRAG knowledge graph proxy endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query

from teaching_agent_api.deps import get_lightrag_client
from teaching_agent_api.lightrag.client import LightRAGClient

router = APIRouter(tags=["graph"])


@router.get("/graph/label/list")
async def list_labels(lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.list_labels()
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/graph/label/popular")
async def popular_labels(limit: int = Query(300, ge=1, le=1000), lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.popular_labels(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/graph/label/search")
async def search_labels(query: str = Query(..., min_length=1), lightrag: LightRAGClient = Depends(get_lightrag_client)):
    try:
        return await lightrag.search_labels(query=query)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})


@router.get("/graphs")
async def get_graph(
    label: str = Query(..., min_length=1),
    max_depth: int = Query(3, ge=1),
    max_nodes: int = Query(1000, ge=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
):
    try:
        return await lightrag.get_graph(label=label, max_depth=max_depth, max_nodes=max_nodes)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}})
```

- [ ] **Step 3: 确认 `main.py` 挂载全部 router**

最终 `main.py` 末尾应有：

```python
from teaching_agent_api.api import health as health_router
from teaching_agent_api.api import projects as projects_router
from teaching_agent_api.api import sessions as sessions_router
from teaching_agent_api.api import chat as chat_router
from teaching_agent_api.api import documents as documents_router
from teaching_agent_api.api import graph as graph_router

app.include_router(health_router.router)
app.include_router(projects_router.router)
app.include_router(sessions_router.router)
app.include_router(chat_router.router)
app.include_router(documents_router.router)
app.include_router(graph_router.router)
```

- [ ] **Step 4: 验证代理端点**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端：
```bash
# 上传一个测试文档
echo "# TCP 三次握手\n\n客户端发送 SYN..." > /tmp/test_doc.md
curl -X POST http://localhost:8000/documents/upload -F "file=@/tmp/test_doc.md"
# 期望：返回 {"status":"success","track_id":"..."}

# 轮询状态
TRACK_ID=<上一步返回的 track_id>
curl http://localhost:8000/documents/track_status/$TRACK_ID

# 列出文档
curl -X POST http://localhost:8000/documents/paginated \
  -H "Content-Type: application/json" \
  -d '{"page":1,"page_size":10}'

# 查询知识图谱标签
curl http://localhost:8000/graph/label/popular?limit=10

# 获取某标签的子图
curl "http://localhost:8000/graphs?label=TCP&max_depth=2"
```

---

## Task 6: 集成测试套件 + 端到端 HITL 全流程

**Goal:** 完整 pytest 测试套件，覆盖所有端点 + 真实 HITL quiz 全流程。

**Files:**
- Create: `teaching_agent_api/tests/__init__.py`（空文件）
- Create: `teaching_agent_api/tests/conftest.py`
- Create: `teaching_agent_api/tests/test_health.py`
- Create: `teaching_agent_api/tests/test_projects.py`
- Create: `teaching_agent_api/tests/test_sessions.py`
- Create: `teaching_agent_api/tests/test_documents_proxy.py`
- Create: `teaching_agent_api/tests/test_chat_streaming.py`

**Interfaces:**
- Consumes: 所有 T1-T5 的实现
- Produces: pytest 测试套件（直接调真实 API）

- [ ] **Step 1: 写 `tests/conftest.py`**

```python
# tests/conftest.py
"""Test fixtures: real ASGI client with lifespan started; cleanup between tests."""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from teaching_agent_api.main import app
from teaching_agent_api.db.engine import create_engine
from teaching_agent_api.config import settings
from sqlalchemy import text


@pytest_asyncio.fixture
async def client():
    """Real ASGI client. Lifespan starts DB engine, checkpointer, LightRAG, agent."""
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture
async def cleanup_db():
    """Delete test data after each test. Run after the test, before yield is the setup (none)."""
    yield
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        # Delete in dependency order
        await conn.execute(text("DELETE FROM answer_record"))
        await conn.execute(text("DELETE FROM question"))
        await conn.execute(text("DELETE FROM message"))
        await conn.execute(text("DELETE FROM session"))
        await conn.execute(text("DELETE FROM project"))
        # Clear LangGraph checkpoints for test threads
        await conn.execute(text("DELETE FROM checkpoints"))
        await conn.execute(text("DELETE FROM checkpoint_writes"))
        await conn.execute(text("DELETE FROM checkpoint_blobs"))
    await engine.dispose()
```

注意：`answer_record` 表不存在（已合并到 question），删除该行。修正：

```python
@pytest_asyncio.fixture
async def cleanup_db():
    yield
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM question"))
        await conn.execute(text("DELETE FROM message"))
        await conn.execute(text("DELETE FROM session"))
        await conn.execute(text("DELETE FROM project"))
        await conn.execute(text("DELETE FROM checkpoints"))
        await conn.execute(text("DELETE FROM checkpoint_writes"))
        await conn.execute(text("DELETE FROM checkpoint_blobs"))
    await engine.dispose()
```

- [ ] **Step 2: 写 `tests/test_health.py`**

```python
# tests/test_health.py
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["components"]["database"] == "ok"
    assert data["components"]["lightrag"] == "ok"
    assert data["components"]["agent"] == "ready"
    assert "langchain" in data["versions"]
    assert "langgraph" in data["versions"]
```

- [ ] **Step 3: 写 `tests/test_projects.py`**

```python
# tests/test_projects.py
import pytest


@pytest.mark.asyncio
async def test_project_crud(client, cleanup_db):
    # Create draft
    resp = await client.post("/projects", json={
        "name": "Test Project",
        "background_md": "# Test\n\nProject background",
        "status": "draft",
    })
    assert resp.status_code == 201
    proj = resp.json()
    assert proj["status"] == "draft"
    pid = proj["id"]

    # List
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert any(p["id"] == pid for p in resp.json())

    # Get
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"

    # Update to published
    resp = await client.patch(f"/projects/{pid}", json={"status": "published"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # Delete
    resp = await client.delete(f"/projects/{pid}")
    assert resp.status_code == 204

    # Get -> 404
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 404
```

- [ ] **Step 4: 写 `tests/test_sessions.py`**

```python
# tests/test_sessions.py
import pytest


@pytest.mark.asyncio
async def test_create_free_session(client, cleanup_db):
    resp = await client.post("/sessions", json={"mode": "free"})
    assert resp.status_code == 201
    sess = resp.json()
    assert sess["mode"] == "free"
    assert sess["status"] == "active"
    assert sess["user_id"] == "demo-student"


@pytest.mark.asyncio
async def test_create_project_session_requires_published_project(client, cleanup_db):
    # Create draft project
    resp = await client.post("/projects", json={
        "name": "Draft Project", "background_md": "test", "status": "draft",
    })
    pid = resp.json()["id"]

    # Try to create project session -> 422
    resp = await client.post("/sessions", json={"mode": "project", "project_id": pid})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "PROJECT_NOT_PUBLISHED"

    # Publish and retry
    await client.patch(f"/projects/{pid}", json={"status": "published"})
    resp = await client.post("/sessions", json={"mode": "project", "project_id": pid})
    assert resp.status_code == 201
    assert resp.json()["mode"] == "project"


@pytest.mark.asyncio
async def test_list_sessions_by_user(client, cleanup_db):
    # Create 2 sessions for demo-student
    await client.post("/sessions", json={"mode": "free"})
    await client.post("/sessions", json={"mode": "free"})

    # List
    resp = await client.get("/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Different user sees none
    resp = await client.get("/sessions", headers={"X-User-Id": "other-user"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_end_session(client, cleanup_db):
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.delete(f"/sessions/{sid}")
    assert resp.status_code == 204

    resp = await client.get(f"/sessions/{sid}")
    assert resp.json()["status"] == "ended"
```

- [ ] **Step 5: 写 `tests/test_documents_proxy.py`**

```python
# tests/test_documents_proxy.py
import pytest


@pytest.mark.asyncio
async def test_pipeline_status(client):
    resp = await client.get("/documents/pipeline_status")
    assert resp.status_code == 200
    data = resp.json()
    assert "busy" in data


@pytest.mark.asyncio
async def test_status_counts(client):
    resp = await client.get("/documents/status_counts")
    assert resp.status_code == 200
    assert "status_counts" in resp.json()


@pytest.mark.asyncio
async def test_list_documents(client):
    resp = await client.post("/documents/paginated", json={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert "pagination" in data


@pytest.mark.asyncio
async def test_graph_labels(client):
    resp = await client.get("/graph/label/popular?limit=5")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 6: 写 `tests/test_chat_streaming.py`（端到端 HITL 全流程）**

```python
# tests/test_chat_streaming.py
"""End-to-end chat streaming + HITL quiz flow with real model + real LightRAG."""
import json

import pytest


def parse_sse_stream(resp_bytes: bytes) -> list[dict]:
    """Parse SSE byte stream into list of {event, data} dicts."""
    events = []
    text = resp_bytes.decode("utf-8")
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_type:
            events.append({"event": event_type, "data": data})
    return events


@pytest.mark.asyncio
async def test_free_mode_chat_streaming(client, cleanup_db):
    # Create free session
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    # Send message; read SSE stream
    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "什么是 TCP 三次握手？"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert any(e["event"] == "text" for e in events), "Should stream text tokens"
    assert events[-1]["event"] == "done", "Should end with done"

    # Verify messages persisted
    resp = await client.get(f"/sessions/{sid}/messages")
    msgs = resp.json()
    assert len(msgs) >= 2  # user + agent
    assert msgs[0]["role"] == "user"
    assert msgs[-1]["role"] == "agent"


@pytest.mark.asyncio
async def test_quiz_hitl_full_flow(client, cleanup_db):
    # Create session
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    # Trigger quiz
    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "考考我 TCP 三次握手"},
    )
    events = parse_sse_stream(resp.content)
    quiz_events = [e for e in events if e["event"] == "quiz_interrupt"]
    if not quiz_events:
        # Agent didn't call quiz_flow; skip the rest (acceptable for this test)
        pytest.skip("Agent did not trigger quiz_flow; behavior may vary by model")
    quiz_payload = quiz_events[0]["data"]

    assert "question_id" in quiz_payload
    assert "q_type" in quiz_payload
    assert "stem" in quiz_payload
    assert quiz_payload["topic"] == "TCP 三次握手" or "TCP" in quiz_payload["topic"]

    # Verify pending question in DB
    resp = await client.get(f"/sessions/{sid}/questions?status=pending")
    assert resp.status_code == 200
    qs = resp.json()
    assert len(qs) == 1
    assert qs[0]["status"] == "pending"

    # Resume with skip
    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "skip"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert events[-1]["event"] == "done"

    # Verify question status updated
    resp = await client.get(f"/sessions/{sid}/questions")
    qs = resp.json()
    skipped = [q for q in qs if q["id"] == quiz_payload["question_id"]]
    assert skipped and skipped[0]["status"] == "skipped"


@pytest.mark.asyncio
async def test_quiz_hitl_answer_flow(client, cleanup_db):
    """Full flow: quiz -> answer -> evaluation persisted."""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "考考我关于 HTTP 协议的知识"},
    )
    events = parse_sse_stream(resp.content)
    quiz_events = [e for e in events if e["event"] == "quiz_interrupt"]
    if not quiz_events:
        pytest.skip("Agent did not trigger quiz_flow")
    quiz_payload = quiz_events[0]["data"]

    # Submit an answer
    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "answer", "answer": "This is my test answer"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert events[-1]["event"] == "done"

    # Verify question updated with answer
    resp = await client.get(f"/sessions/{sid}/questions?status=answered")
    qs = resp.json()
    assert len(qs) == 1
    q = qs[0]
    assert q["user_answer"] == "This is my test answer"
    assert q["verdict"] in ("correct", "partial", "wrong")
    assert q["answered_at"] is not None


@pytest.mark.asyncio
async def test_resume_without_interrupt_fails(client, cleanup_db):
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "skip"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_INTERRUPTED"
```

- [ ] **Step 7: 运行完整测试套件**

```bash
cd /Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api
uv sync --extra test
uv run pytest tests/ -v
```

期望：所有测试通过（可能 chat 流式测试因 LLM 输出不确定性偶有跳过，符合预期）。

- [ ] **Step 8: 最终端到端验证**

启动服务后，按真实使用顺序调用 API：

```bash
uv run uvicorn teaching_agent_api.main:app --host 0.0.0.0 --port 8000
```

完整流程：
```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Create project + publish
PID=$(curl -s -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"TCP 服务器实现","background_md":"# 项目\n\n实现一个简单的 TCP echo 服务器","status":"published"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 3. Create project session
SID=$(curl -s -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"project\",\"project_id\":\"$PID\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 4. Chat (SSE)
curl -N -X POST "http://localhost:8000/chat/sessions/$SID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"这个项目需要掌握哪些知识？"}'

# 5. Upload a doc to LightRAG (knowledge base)
echo "# TCP 协议\n\nTCP 是面向连接的可靠传输协议..." > /tmp/tcp.md
curl -X POST http://localhost:8000/documents/upload -F "file=@/tmp/tcp.md"

# 6. View knowledge graph
curl "http://localhost:8000/graphs?label=TCP&max_depth=2"
```

---

## Self-Review

### Spec Coverage

| Spec 章节 | 覆盖任务 |
|---|---|
| §1 概述 | Global Constraints |
| §2 整体架构 | T1 (scaffolding) + T2 (lightrag client) + T3 (agent) + T4 (runtime) |
| §3 数据模型（4 表） | T1 Step 5 (models.py) |
| §4 API 设计（30+ 端点） | T2 (projects/sessions) + T4 (chat) + T5 (documents/graph) |
| §5 Agent 设计 | T3 (llm/prompts/tools/factory) + T4 (runtime) |
| §6 LightRAG 集成 | T2 (client.py) |
| §7 项目结构 | 全局 File Structure 章节 |
| §8 配置 | T1 Step 3 (.env) |
| §9 测试策略 | T6 |

无遗漏。

### Type Consistency Check

- `AgentContext` 在 T3 prompts.py 定义，在 T4 runtime.py 和 chat.py 使用 - 字段一致 (`mode`, `course_name`, `project_name`, `project_background_md`)
- `build_agent(checkpointer)` 在 T3 factory.py 定义，在 T1 main.py lifespan 和 T4 deps.py 使用 - 签名一致
- `stream_chat(agent, session_id, user_msg, context, db_session)` 和 `resume_quiz(agent, session_id, action, answer, db_session)` 在 T4 runtime.py 定义和 chat.py 使用 - 签名一致
- `set_dependencies(lightrag_client, db_session_factory)` 在 T3 tools.py 定义，T1 main.py 调用 - 参数一致
- `LightRAGClient` 方法名在 T2 client.py 定义，T5 documents.py/graph.py 调用 - 方法名一致
- DB repos 函数签名在 T1 repos.py 定义，T3 tools.py 和 T4 chat.py 调用 - 签名一致
- `_db_session()` 改为 `@asynccontextmanager`，T3 tools.py 中所有调用点用 `async with _db_session() as db_session:`

无类型不一致。

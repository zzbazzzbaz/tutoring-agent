# 教学 Agent API 设计（FastAPI + LightRAG 重构版）

| 项 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-07-19 |
| 状态 | 设计定稿 |
| 目标 | 用 FastAPI 重构教学 Agent 后端，RAG 切换为 LightRAG（HTTP 代理），单 agent 双模式（free/project），SSE 流式响应，简化为极简版（无跨会话画像/错题本/重练） |
| 上一版 | [2026-07-17-teaching-agent-prototype-design.md](./2026-07-17-teaching-agent-prototype-design.md)（Notebook 原型） |

---

## 1. 概述

### 1.1 定位

FastAPI 重构版教学 Agent 后端，核心验证：

1. **苏格拉底式追问引导** -- 不直接给答案，通过追问引导学生推导
2. **实时出题检验（HITL）** -- 对话中 Agent 判断时机调用 `quiz_flow` 工具，interrupt 暂停等待学生答题
3. **LightRAG 知识检索** -- RAG 委托 LightRAG（知识图谱 + 向量），后端不再自建 RAG 流水线
4. **流式响应** -- SSE 推送 token，前端逐字渲染

### 1.2 与上一版的差异

| 维度 | 上一版（Notebook 原型） | 本版（FastAPI 重构） |
|---|---|---|
| 入口 | Jupyter Notebook | FastAPI HTTP API |
| RAG | 自建 pgvector + GraphRAG + LLM 图谱构建 | LightRAG HTTP 服务（KG + RAG 一体） |
| Agent 数量 | 3 个（free/project/review） | 1 个，双模式（free/project） |
| 工具 | search + quiz + end_session | search + quiz（去掉 end_session） |
| 持久化 | Session/Message/Question/AnswerRecord/Mistake/Profile/KB/Chunk/KP/Edge | Project/Session/Message/Question（Question 合并 AnswerRecord，极简版） |
| 跨会话记忆 | StudentProfile + MistakeItem | 不做 |
| 流式 | 无 | SSE（4 种事件） |
| 认证 | 无 | 无（支持 `X-User-Id` 头） |
| 工程化 | Notebook 调试 | uv + src layout + 分层 routers/services/repos |

### 1.3 关键约束

- **uv 工程**，Python 3.13，**LangChain/LangGraph 1.x**（严禁 0.3.x API）
- **真实模型**：DashScope `qwen3.6-flash`（与 LightRAG 部署一致），不 mock
- **真实 LightRAG**：调 `http://101.35.223.219:15434`，不 mock
- **真实 DB**：`postgresql+asyncpg://root:...@101.35.223.219:15433/teaching-agent-0718`
- **不上 TDD**：测试直接调真实 API 验证
- **本轮只覆盖后端**：前端另起一轮
- **前端复用 lightrag_webui 技术栈**（React 19 + Vite + Bun + Tailwind + Radix + Zustand + axios）

### 1.4 已验证的技术栈

| 组件 | 版本 | 关键配置 |
|---|---|---|
| Python | 3.13 | uv 管理 |
| FastAPI | >= 0.115 | 异步 ASGI + lifespan |
| uvicorn | >= 0.30 | standard extras |
| sse-starlette | >= 2.1 | SSE 响应 + 心跳 |
| langchain | >= 1.3 | `create_agent` + `@dynamic_prompt` 中间件 |
| langgraph | >= 1.2 | `interrupt` + `Command` + `astream_events(version="v3")` |
| langgraph-checkpoint-postgres | >= 3.1 | `AsyncPostgresSaver.from_conn_string` |
| langchain-openai | >= 1.3 | `ChatOpenAI` DashScope 兼容模式 |
| httpx | >= 0.27 | LightRAG 异步客户端 |
| SQLModel | >= 0.0.22 | ORM + Pydantic 合一 |
| asyncpg | >= 0.30 | PG async driver |
| psycopg[binary] | >= 3.2 | AsyncPostgresSaver 依赖 |
| pydantic-settings | >= 2.5 | `.env` 配置 |
| python-multipart | >= 0.0.12 | FastAPI 文件上传 |
| DashScope LLM | qwen3.6-flash | `extra_body={"enable_thinking": False}`，温度 0.7 |
| LightRAG | 1.5.4 | `http://101.35.223.219:15434`，X-API-Key 认证 |
| PostgreSQL | 17 + pgvector | `101.35.223.219:15433`，db=`teaching-agent-0718` |

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     前端 (下一轮)                              │
│   lightrag_webui 技术栈：React 19 + Vite + Tailwind + axios   │
│   复用：文档上传 / 知识图谱可视化 / chat UI                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (单一 baseUrl)
┌──────────────────────────▼───────────────────────────────────┐
│              teaching_agent_api (FastAPI)                     │
│                                                                │
│  api/                  (薄路由层)                              │
│    chat.py             POST /chat/sessions/{id}/messages (SSE)│
│                        POST /chat/sessions/{id}/quiz/resume   │
│    sessions.py         CRUD /sessions, /messages, /questions   │
│    projects.py         CRUD /projects                          │
│    documents.py        代理 LightRAG /documents/*              │
│    graph.py            代理 LightRAG /graph/*, /graphs         │
│    health.py           GET /health                            │
│                                                                │
│  agent/                (LangGraph agent, 1.x 最佳实践)         │
│    llm.py              get_llm() -> ChatOpenAI(qwen3.6-flash) │
│    prompts.py          GUIDANCE_PROMPT_FREE/PROJECT           │
│                        + @dataclass AgentContext               │
│                        + @dynamic_prompt teaching_prompt       │
│    tools.py            search_knowledge / quiz_flow            │
│                        + QuizOutput / EvaluationOutput         │
│    factory.py          build_agent(checkpointer) 单例          │
│    runtime.py          stream_chat / resume_quiz -> SSE        │
│                                                                │
│  lightrag/             (LightRAG 客户端封装)                   │
│    client.py           LightRAGClient(httpx.AsyncClient)      │
│    schemas.py          LightRAG 响应 Pydantic 模型             │
│                                                                │
│  db/                   (持久层)                                │
│    engine.py           async engine + sessionmaker + lifespan │
│    models.py           SQLModel 表 (4 张)                     │
│    repos.py            仓储函数 (async)                       │
│                                                                │
│  schemas/              (API 入参/出参 Pydantic)                │
│    chat.py / session.py / project.py                          │
│                                                                │
│  main.py               FastAPI app + lifespan + CORS           │
│  config.py             Settings (pydantic-settings)           │
│  deps.py               FastAPI 依赖注入                         │
└────────────┬───────────────────┬──────────────────────────────┘
             │ asyncpg            │ httpx (X-API-Key)
┌────────────▼──────────┐ ┌──────▼─────────────────────────────┐
│  PostgreSQL + pgvector │ │  LightRAG Server (1.5.4)          │
│  db=teaching-agent-0718│ │  http://101.35.223.219:15434      │
│                        │ │                                    │
│  业务表 (4 张):        │ │  /documents/* (上传/列表/删除)    │
│   - project            │ │  /query (内部调用)                │
│   - session            │ │  /query/data (内部调用)            │
│   - message            │ │  /graphs, /graph/label/*          │
│   - question           │ │                                    │
│   (含合并的答题字段)    │ │  内部:                            │
│                        │ │   - PG (db=lightrag)              │
│  LangGraph 检查点表    │ │   - DashScope qwen3.6-flash       │
│  (AsyncPostgresSaver   │ │   - DashScope text-embedding-v4   │
│   .setup() 自建)       │ │   - NetworkX 图                   │
└────────────────────────┘ └────────────────────────────────────┘
             │
┌────────────▼─────────────────────────────────────────────────┐
│  DashScope (OpenAI 兼容端点)                                  │
│  qwen3.6-flash (agent LLM) + text-embedding-v4 (LightRAG 用) │
└──────────────────────────────────────────────────────────────┘
```

### 核心设计决策

1. **代理模式**：前端只调我们后端，后端代理 LightRAG 的 `/documents/*` 和 `/graph/*`（注入 `X-API-Key`，前端不知道 key）
2. **极简版数据**：4 张业务表，去掉 StudentProfile/MistakeItem/Review/KBDocument/Chunk/KP/Edge
3. **单库 + 提示词注入**：LightRAG 用默认 workspace（所有文档一个库），project 模式 = system prompt 注入项目背景
4. **单 agent + 动态 prompt**：free/project 共用一个 agent 实例，通过 `@dynamic_prompt` 中间件 + `AgentContext` 在 invoke 时注入模式信息
5. **Question 合并 AnswerRecord**：1:1 关系合并为一张表，少一次 JOIN，quiz_flow 逻辑更清晰（INSERT pending -> UPDATE 同行填答题字段）
6. **SSE 4 种事件**：text / quiz_interrupt / done / error（不引入 quiz_result，结构化数据走 REST）
7. **LightRAG `only_need_context=True`**：agent 自带 LLM，仅需检索上下文，不调 LightRAG 的 LLM 生成
8. **不上 Alembic**：MVP 用 `SQLModel.metadata.create_all()` 幂等建表
9. **不上 RetryPolicy 中间件**：MVP 简化，LLM 偶发失败由用户重试

---

## 3. 数据模型

### 3.1 表清单（4 张业务表 + LangGraph 检查点表）

| 实体 | 用途 | 关键关系 |
|---|---|---|
| **Project** | 项目元数据（注入 system prompt） | 1:N Session |
| **Session** | 会话（id = LangGraph thread_id） | N:1 Project, 1:N Message/Question |
| **Message** | 对话消息（user/agent） | N:1 Session |
| **Question** | 题目 + 答题记录（合并 1:1） | N:1 Session |
| ~~StudentProfile/MistakeItem/KBDocument/Chunk/KP/Edge~~ | 极简版不建 | - |
| LangGraph 检查点表 | interrupt/resume 编排状态 | `AsyncPostgresSaver.setup()` 自建 |

### 3.2 SQLModel 表定义

```python
# db/models.py
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import JSON, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP


class Project(SQLModel, table=True):
    """项目元数据（注入 system prompt）"""
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
    """会话；id 同时作为 LangGraph thread_id"""
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
    """对话消息；业务查询用，LangGraph 自身消息历史在 checkpoint 表"""
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
    """题目 + 答题记录（1:1 合并）"""
    __tablename__ = "question"

    # === 题目字段（出题时填写，interrupt 之前） ===
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
    options: Optional[list] = Field(default=None, sa_column=Column(JSON))  # short 题为 null
    answer: str = Field(sa_column=Column(Text))  # 正确答案
    analysis: Optional[str] = Field(default=None, sa_column=Column(Text))  # 题目解析

    # === 状态字段 ===
    status: str = Field(default="pending", max_length=20, index=True)  # pending/answered/skipped

    # === 答题字段（resume 时填写，nullable） ===
    user_answer: Optional[str] = Field(default=None, sa_column=Column(Text))
    verdict: Optional[str] = Field(default=None, max_length=20)  # correct/partial/wrong
    diagnosis: Optional[str] = Field(default=None, sa_column=Column(Text))  # 错因诊断 + 评估分析

    # === 时间戳 ===
    created_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    answered_at: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))

    session: "Session" = Relationship(back_populates="questions")
```

### 3.3 关键设计决策

1. **UUID 主键**：所有表用 `uuid4`，避免顺序 ID 泄露
2. **`session.id` = LangGraph `thread_id`**：会话 ID 直接复用，无需映射
3. **`session.user_id`**：默认 `"demo-student"`，支持 `X-User-Id` 头覆盖（前向兼容未来认证）
4. **`session.project_id` ON DELETE SET NULL**：删项目不级联删会话，保留历史对话
5. **`message/question` ON DELETE CASCADE**：删会话级联清子记录
6. **Question 合并 AnswerRecord**：1:1 关系合并，`status` 区分 pending/answered/skipped；幂等性靠 `(session_id, topic, status='pending')` 查询
7. **`question.analysis`（题目解析）+ `question.diagnosis`（评估诊断）字段名清晰区分**
8. **不存 `tool_events`**：MVP 简化，agent 工具调用细节若需调试可查 LangGraph state
9. **不存 KnowledgePoint/Chunk**：全部委托 LightRAG

### 3.4 仓储层（`db/repos.py`）

纯函数式 async 仓储，无类封装（YAGNI）：

```python
# Session
async def create_session(session: AsyncSession, mode: str, user_id: str, project_id: UUID | None) -> Session
async def get_session(session: AsyncSession, session_id: UUID) -> Session | None
async def list_sessions(session: AsyncSession, user_id: str, status: str | None = None, mode: str | None = None, limit: int = 20, offset: int = 0) -> list[Session]
async def update_session_active(session: AsyncSession, session_id: UUID) -> None  # 更新 last_active_at
async def end_session(session: AsyncSession, session_id: UUID) -> None  # status="ended"

# Message
async def save_message(session: AsyncSession, session_id: UUID, role: str, content: str) -> Message
async def list_messages(session: AsyncSession, session_id: UUID, limit: int = 100, offset: int = 0) -> list[Message]

# Question
async def upsert_question(session: AsyncSession, session_id: UUID, topic: str, quiz: QuizOutput) -> Question  # 幂等 INSERT ... ON CONFLICT
async def get_pending_question(session: AsyncSession, session_id: UUID, topic: str) -> Question | None  # 幂等检查
async def update_question(session: AsyncSession, question_id: UUID, **fields) -> None  # 答题时 UPDATE 同一行
async def list_questions(session: AsyncSession, session_id: UUID, status: str | None = None) -> list[Question]

# Project
async def create_project(session: AsyncSession, name: str, background_md: str, status: str = "draft") -> Project
async def get_project(session: AsyncSession, project_id: UUID) -> Project | None
async def list_projects(session: AsyncSession, status: str | None = None) -> list[Project]
async def update_project(session: AsyncSession, project_id: UUID, **fields) -> Project
async def delete_project(session: AsyncSession, project_id: UUID) -> None
```

### 3.5 数据库初始化

```python
# db/engine.py
async def init_db(engine):
    """lifespan 启动时调用，幂等"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
```

```python
# main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. DB engine + 业务表
    engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
    await init_db(engine)

    # 2. LangGraph checkpointer（建检查点表）
    async with AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL) as checkpointer:
        await checkpointer.setup()  # idempotent

        # 3. LightRAG client
        lightrag_client = LightRAGClient(
            base_url=settings.LIGHTRAG_BASE_URL,
            api_key=settings.LIGHTRAG_API_KEY,
        )
        await lightrag_client.start()

        # 4. Agent 单例 + 工具依赖注入
        from .agent.tools import set_dependencies
        set_dependencies(lightrag_client=lightrag_client, db_session_factory=db_session_factory)
        agent = build_agent(checkpointer)

        # 注入 app.state
        app.state.engine = engine
        app.state.checkpointer = checkpointer
        app.state.lightrag_client = lightrag_client
        app.state.agent = agent

        yield

    # 清理
    await lightrag_client.close()
    await engine.dispose()
```

### 3.6 DB 连接

```
DATABASE_URL = postgresql+asyncpg://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718
```

- 同实例同端口，不同 database：`teaching-agent-0718`（业务 + LangGraph checkpoint）vs `lightrag`（LightRAG 自己的 KV/vector/graph）
- 连接池：`pool_size=10, max_overflow=20`

---

## 4. API 设计

### 4.1 API 总览（无 `/v1` 前缀，匹配 lightrag_webui 路径便于前端复用）

| 端点 | 方法 | 用途 | 流式 |
|---|---|---|---|
| **Chat（核心）** | | | |
| `/chat/sessions/{session_id}/messages` | POST | 发送消息，SSE 流式回复 | ✓ |
| `/chat/sessions/{session_id}/quiz/resume` | POST | 提交答题，SSE 流式继续 | ✓ |
| **Sessions** | | | |
| `/sessions` | POST | 创建会话 | |
| `/sessions` | GET | 列出当前用户会话 | |
| `/sessions/{session_id}` | GET | 会话详情 | |
| `/sessions/{session_id}` | DELETE | 结束/删除会话 | |
| `/sessions/{session_id}/messages` | GET | 会话消息历史 | |
| `/sessions/{session_id}/questions` | GET | 会话题目列表（含答题记录） | |
| **Projects** | | | |
| `/projects` | POST | 创建项目 | |
| `/projects` | GET | 列出项目 | |
| `/projects/{project_id}` | GET | 项目详情 | |
| `/projects/{project_id}` | PATCH | 更新项目 | |
| `/projects/{project_id}` | DELETE | 删除项目 | |
| **Documents（代理 LightRAG）** | | | |
| `/documents/upload` | POST | 上传文件（multipart） | |
| `/documents/text` | POST | 插入单段文本 | |
| `/documents/texts` | POST | 插入多段文本 | |
| `/documents/scan` | POST | 触发目录扫描 | |
| `/documents/track_status/{track_id}` | GET | 轮询上传状态 | |
| `/documents/pipeline_status` | GET | 流水线状态 | |
| `/documents/status_counts` | GET | 按状态计数 | |
| `/documents/paginated` | POST | 分页列表 | |
| `/documents/delete_document` | DELETE | 删除指定文档 | |
| **Graph（代理 LightRAG）** | | | |
| `/graph/label/list` | GET | 所有标签 | |
| `/graph/label/popular` | GET | 热门标签 | |
| `/graph/label/search` | GET | 搜索标签 | |
| `/graphs` | GET | 获取子图 | |
| **Health** | | | |
| `/health` | GET | 健康检查（含 LightRAG 连通性） | |

> **不暴露**：`DELETE /documents`（清空全部，危险）、`/documents/clear_cache`、`/documents/cancel_pipeline`、`/documents/reprocess_failed`、`/query`、`/query/stream`、`/query/data`（这些是 LightRAG 内部 API，仅 agent 内部调用，不对前端开放）。

### 4.2 SSE 事件协议（基于 `sse-starlette`）

**事件类型（最小集，4 种）**：

| event | data | 时机 | 前端动作 |
|---|---|---|---|
| `text` | `{"content": "token"}` | agent 流式输出 token | 追加到当前消息缓冲 |
| `quiz_interrupt` | `{"question_id": "...", "topic": "...", "q_type": "...", "stem": "...", "options": [...]}` | quiz_flow 调 `interrupt()` 暂停 | 切换到答题 UI，存 payload |
| `done` | `{}` | 流结束（无论是否 interrupt） | 关闭 SSE 连接 |
| `error` | `{"message": "...", "code": "..."}` | 异常 | 显示错误，关闭连接 |

**关键决策**：
- **不引入 `quiz_result` 事件**：评估结果走 REST 查询（`GET /sessions/{id}/questions`）。SSE 只负责实时文本流，REST 负责结构化数据，职责分离。
- **`quiz_interrupt` 后必发 `done`**：`done` 表示"本 SSE 流结束"，不表示"会话结束"。前端见 `quiz_interrupt` 切换 UI，见 `done` 关流。
- **心跳**：sse-starlette 内置 keepalive（默认 15s `:ping\n\n`），防止长 LLM 响应超时。
- **错误格式**：HTTP 200 + SSE `error` 事件（而非 HTTP 500），因为流已开始时改 HTTP 状态码来不及。

**SSE 帧格式**：
```
event: text
data: {"content":"TCP"}

event: text
data: {"content":"三次"}

event: quiz_interrupt
data: {"question_id":"...","topic":"TCP三次握手","q_type":"single","stem":"...","options":["A","B","C","D"]}

event: done
data: {}
```

### 4.3 Chat 端点（核心）

#### `POST /chat/sessions/{session_id}/messages`（SSE）

**请求**：
```http
POST /chat/sessions/{session_id}/messages
Content-Type: application/json
X-User-Id: demo-student  # 可选，默认 demo-student

{"content": "什么是TCP三次握手？"}
```

**响应**：`text/event-stream`

**后端流程**：
1. 取 Session（校验存在、`user_id` 匹配、`status == "active"`）
2. 查 LangGraph state，若处于 interrupt 状态 -> 返回 409 Conflict（前端应先调 `/quiz/resume` 跳过或答题）
3. 落库：`save_message(session_id, role="user", content)`
4. 构建 `AgentContext`：
   - `mode` = `session.mode`
   - `course_name` = `settings.COURSE_NAME`
   - 若 project 模式：查 Project，填 `project_name` + `project_background_md`
5. 调 `stream_chat(agent, session_id, user_msg, context, db_session)` 生成 SSE 流
6. 更新 `session.last_active_at`

**错误码**：
- 404: session 不存在
- 403: user_id 不匹配
- 409: session 已结束 / 处于 interrupt 待恢复状态
- 422: 请求体校验失败

#### `POST /chat/sessions/{session_id}/quiz/resume`（SSE）

**请求**：
```http
POST /chat/sessions/{session_id}/quiz/resume
Content-Type: application/json

{"action": "answer", "answer": "SYN+ACK"}
# 或
{"action": "skip"}
```

**响应**：`text/event-stream`（agent 看到评估结果后继续追问的流式回复）

**后端流程**：
1. 取 Session，校验
2. 查 LangGraph state，**必须处于 interrupt 状态**，否则 409
3. 调 `resume_quiz(agent, session_id, action, answer)`
4. 流结束后落库 agent 最终消息
5. 更新 `session.last_active_at`

**错误码**：
- 404: session 不存在
- 409: session 不在 interrupt 状态（无可恢复的 quiz）
- 422: `action="answer"` 但 `answer` 缺失

### 4.4 Sessions 端点

#### `POST /sessions`
```json
// 请求
{"mode": "project", "project_id": "uuid-..."}

// 响应 201
{"id": "uuid", "user_id": "demo-student", "mode": "project",
 "project_id": "uuid", "project_name": "TCP 服务器实现",
 "title": null, "status": "active",
 "created_at": "...", "last_active_at": "..."}
```

校验：`mode="project"` 时 `project_id` 必填且对应项目 `status="published"`。

#### `GET /sessions?status=active&mode=project&limit=20&offset=0`
按 `X-User-Id` 头过滤当前用户会话，按 `last_active_at desc` 排序。

#### `GET /sessions/{session_id}`
返回单个会话（含 `project_name` join 显示）。

#### `DELETE /sessions/{session_id}`
软删除：`status="ended"`，**不级联删数据**（保留历史）。返回 204。

#### `GET /sessions/{session_id}/messages?limit=100&offset=0`
按 `created_at asc` 排序，返回消息列表。用于前端加载历史对话。

#### `GET /sessions/{session_id}/questions?status=answered`
返回题目列表（含答题记录字段）。前端在 quiz resume 流结束后调此端点刷新结果卡片。

### 4.5 Projects 端点

标准 CRUD，无需特殊说明。

```json
// POST /projects
{"name": "TCP 服务器实现", "background_md": "# 项目背景\n\n实现一个基于...", "status": "draft"}

// PATCH /projects/{id}
{"status": "published"}  // 发布后才能被 session 引用
```

### 4.6 Documents / Graph 代理端点（透传）

**代理策略**：所有 `/documents/*` 和 `/graph/*` 端点都是透传代理，后端不做业务逻辑，只：
1. 注入 `X-API-Key` 头（前端不知道 LightRAG key）
2. 转发 multipart body / JSON body / query params
3. 透传响应（包括状态码、Content-Type、body）

```python
# api/documents.py 关键实现
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
):
    content = await file.read()
    return await lightrag.upload_file(content, file.filename, file.content_type)
```

**为什么透传而不抽象**：
- lightrag_webui 前端代码已定义了请求/响应结构，透传 = 100% 兼容
- LightRAG API 已稳定（1.5.4），无需二次抽象
- 后端代码量最小

### 4.7 Health 端点

```json
// GET /health
{
  "status": "healthy",
  "components": {
    "database": "ok",
    "lightrag": "ok",
    "agent": "ready"
  },
  "versions": {
    "api": "0.1.0",
    "langchain": "1.x.x",
    "langgraph": "1.x.x"
  }
}
```

### 4.8 Pydantic API Schemas（与 ORM 解耦）

```python
# schemas/chat.py
class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)

class QuizResumeRequest(BaseModel):
    action: Literal["answer", "skip"]
    answer: Optional[str] = None

    @model_validator(mode="after")
    def check_answer(self):
        if self.action == "answer" and not self.answer:
            raise ValueError("answer is required when action='answer'")
        return self

# schemas/session.py
class SessionCreate(BaseModel):
    mode: Literal["free", "project"]
    project_id: Optional[UUID] = None

class SessionOut(BaseModel):
    id: UUID
    user_id: str
    mode: str
    project_id: Optional[UUID]
    project_name: Optional[str] = None  # join 显示
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

# schemas/project.py
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    background_md: str = Field(min_length=1)
    status: Literal["draft", "published"] = "draft"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    background_md: Optional[str] = None
    status: Optional[Literal["draft", "published"]] = None

class ProjectOut(BaseModel):
    id: UUID
    name: str
    background_md: str
    status: str
    created_at: datetime
    updated_at: datetime
```

### 4.9 错误响应规范

统一错误格式：
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session uuid-... not found"
  }
}
```

错误码清单：
- `SESSION_NOT_FOUND` (404)
- `SESSION_ENDED` (409)
- `SESSION_INTERRUPTED` (409, 需先 resume)
- `SESSION_NOT_INTERRUPTED` (409, resume 但无 interrupt)
- `PROJECT_NOT_FOUND` (404)
- `PROJECT_NOT_PUBLISHED` (422, 创建 project session 时项目未发布)
- `VALIDATION_ERROR` (422)
- `LIGHTRAG_ERROR` (502, 代理 LightRAG 失败，附上游状态码)
- `INTERNAL_ERROR` (500)

### 4.10 CORS 配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP，前端独立部署
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # SSE 需要
)
```

---

## 5. Agent 设计

### 5.1 System Prompts（`agent/prompts.py`）

两个模板，project 模式 = free 模式 + 项目背景注入。核心原则共用：

```python
GUIDANCE_PROMPT_FREE = """你是一位苏格拉底式教学助手，课程是《{course_name}》。

## 核心原则
1. 绝不直接给出答案。通过提问引导学生自己推导出结论。
2. 当学生提问或讨论某个概念时，先调用 search_knowledge 检索相关知识，再基于检索内容设计追问。
3. 如果检索结果为空，告诉学生"这个问题可能超出当前课程知识库范围"，引导回课程内容。
4. 根据学生的回答判断理解程度：
   - 理解有误 -> 针对性追问，暴露矛盾
   - 理解部分 -> 追问未覆盖的部分
   - 理解到位 -> 可以调用 quiz_flow 出题检验
5. 学生说"考考我"/"出题"/"测验"时，调用 quiz_flow 出题。
6. 每次追问保持上下文连贯，不要突兀跳转话题。

## 当前会话
学生正在进行自由学习，围绕课程知识自由探索。

## 可用工具
- search_knowledge(query): 检索课程知识库（含知识图谱），返回相关知识片段
- quiz_flow(topic): 出一道题并等待学生作答，返回评估结果
"""

GUIDANCE_PROMPT_PROJECT = """你是一位苏格拉底式教学助手，课程是《{course_name}》。

## 核心原则
[同上 1-6]

## 当前项目
学生正在学习项目：{project_name}

## 项目背景
{project_background_md}

请以项目背景为情境展开追问，将课程知识应用到项目场景中。鼓励学生思考如何将所学知识用于解决项目中的实际问题。

## 可用工具
[同上]
"""
```

`@dynamic_prompt` 中间件 + `AgentContext` dataclass：

```python
from dataclasses import dataclass
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dataclass
class AgentContext:
    mode: Literal["free", "project"]
    course_name: str
    project_name: str = ""
    project_background_md: str = ""

@dynamic_prompt
def teaching_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    if ctx.mode == "project":
        return GUIDANCE_PROMPT_PROJECT.format(
            course_name=ctx.course_name,
            project_name=ctx.project_name,
            project_background_md=ctx.project_background_md,
        )
    return GUIDANCE_PROMPT_FREE.format(course_name=ctx.course_name)
```

### 5.2 Structured Output Schemas（`agent/tools.py`）

```python
class QuizOutput(BaseModel):
    """出题 LLM 结构化输出"""
    q_type: Literal["single", "multi", "short"] = Field(description="题型")
    stem: str = Field(description="题干")
    options: Optional[list[str]] = Field(None, description="选项列表，short 题为 null")
    answer: str = Field(description="正确答案（single: 选项文本；multi: 'A,C,D'；short: 要点列表）")
    analysis: str = Field(description="题目解析")

class EvaluationOutput(BaseModel):
    """评估 LLM 结构化输出"""
    verdict: Literal["correct", "partial", "wrong"] = Field(description="判定结果")
    diagnosis: str = Field(description="错因诊断（答对时为空字符串）")
    analysis: str = Field(description="评分解析")
```

**简化决策**：
- 去掉 `correct_answer`（已在 QuizOutput.answer 中）
- 去掉 `follow_up_hint`（agent 自然生成后续追问）
- `method="function_calling"`：DashScope 兼容 OpenAI function calling，比 json_mode 稳定

### 5.3 Tools（`agent/tools.py`）

#### search_knowledge -- 调 LightRAG 检索

```python
@tool
async def search_knowledge(query: str) -> str:
    """检索课程知识库（知识图谱 + RAG），返回相关知识片段。

    当学生提问或讨论某个概念时，先调用此工具检索相关知识，
    再基于检索内容设计苏格拉底式追问。检索结果包含向量匹配和知识图谱扩展的片段。

    Args:
        query: 检索关键词，需包含完整上下文（消除代词指代）
    """
    lightrag = _get_lightrag_client()
    try:
        result = await lightrag.query(
            query=query,
            mode="mix",                  # KG + 向量，LightRAG 推荐
            only_need_context=True,       # 不调 LightRAG 的 LLM，仅返回检索上下文
            include_references=True,
        )
    except Exception as e:
        return f"知识库检索失败: {e}"

    context = (result.get("response") or "").strip()
    if not context:
        return "未检索到相关内容，该问题可能超出当前课程知识库范围"
    return context
```

**为什么 `only_need_context=True`**：agent 自带 LLM（qwen3.6-flash），只需 LightRAG 检索上下文，不需要 LightRAG 二次调 LLM 生成答案（避免双 LLM 调用浪费 token + 时延）。

#### quiz_flow -- HITL 出题 + 评估

```python
@tool
async def quiz_flow(topic: str, config: RunnableConfig) -> str:
    """出一道关于指定知识点的题目，等待学生作答后返回评估结果。

    当学生说"考考我"、需要检验理解程度、或你判断时机成熟时调用此工具。
    调用后会暂停等待学生答题，学生提交答案后自动判分。

    Args:
        topic: 要出题的知识点名称
    """
    session_id = config["configurable"]["thread_id"]

    # === 幂等检查（resume 时复用，避免重复出题） ===
    pending = await get_pending_question(session_id, topic)
    if pending:
        quiz = pending  # 复用已生成的题目
    else:
        # === 首次：检索 + 生成 ===
        context = await _search_for_quiz(topic)
        quiz = await _generate_quiz(topic, context)
        await upsert_question(session_id, topic, quiz, status="pending")  # 幂等 upsert

    # === interrupt：首次 raise，resume 时返回学生答案 ===
    student_answer = interrupt({
        "question_id": str(quiz.id),
        "topic": topic,
        "q_type": quiz.q_type,
        "stem": quiz.stem,
        "options": quiz.options,
    })

    # === 以下只在 resume 时执行一次 ===
    if student_answer.get("action") == "skip":
        await update_question(quiz.id, status="skipped", answered_at=datetime.utcnow())
        return "学生跳过了本题。请继续对话，了解学生的疑虑。"

    answer = student_answer.get("answer", "")
    evaluation = await _evaluate_answer(quiz, answer)

    await update_question(
        quiz.id,
        status="answered",
        user_answer=answer,
        verdict=evaluation.verdict,
        diagnosis=evaluation.diagnosis,
        answered_at=datetime.utcnow(),
    )

    return (
        f"判定: {evaluation.verdict}\n"
        f"错因诊断: {evaluation.diagnosis}\n"
        f"正确答案: {quiz.answer}\n"
        f"解析: {evaluation.analysis}"
    )
```

Helper 函数（模块内私有）：

```python
async def _search_for_quiz(topic: str) -> str:
    """出题前先检索相关知识作为素材"""
    lightrag = _get_lightrag_client()
    result = await lightrag.query(query=topic, mode="mix", only_need_context=True)
    return result.get("response", "")

async def _generate_quiz(topic: str, context: str) -> QuizOutput:
    """LLM 结构化出题"""
    llm = get_llm().with_structured_output(QuizOutput, method="function_calling")
    return await llm.ainvoke(QUIZ_GENERATION_PROMPT.format(
        course_name=settings.COURSE_NAME,
        topic=topic,
        context=context or "（无检索结果）",
    ))

async def _evaluate_answer(quiz: Question, user_answer: str) -> EvaluationOutput:
    """LLM 结构化评估"""
    llm = get_llm().with_structured_output(EvaluationOutput, method="function_calling")
    return await llm.ainvoke(EVALUATION_PROMPT.format(
        stem=quiz.stem,
        q_type=quiz.q_type,
        correct_answer=quiz.answer,
        student_answer=user_answer,
    ))
```

出题/评估 prompt（模块内常量）：

```python
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
```

### 5.4 LLM 配置（`agent/llm.py`）

```python
from langchain_openai import ChatOpenAI

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.LLM_MODEL,                  # qwen3.6-flash
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,       # https://dashscope.aliyuncs.com/compatible-mode/v1
        temperature=0.7,                            # 教学场景适度发散
        extra_body={"enable_thinking": False},       # DashScope 关闭思考输出
    )
```

### 5.5 依赖注入模式（工具访问 LightRAGClient + DB）

工具函数不能直接用 FastAPI `Depends`（不在请求上下文）。用模块级容器，lifespan 启动时注入：

```python
# agent/tools.py
_state: dict = {}

def set_dependencies(*, lightrag_client: LightRAGClient, db_session_factory):
    _state["lightrag"] = lightrag_client
    _state["db_factory"] = db_session_factory

def _get_lightrag_client() -> LightRAGClient:
    return _state["lightrag"]

async def _get_db_session() -> AsyncSession:
    """工具内部获取 DB session"""
    factory = _state["db_factory"]
    async with factory() as session:
        yield session
```

```python
# main.py lifespan
from teaching_agent_api.agent.tools import set_dependencies
set_dependencies(lightrag_client=lightrag_client, db_session_factory=db_session_factory)
```

### 5.6 Agent Factory（`agent/factory.py`）

```python
from langchain.agents import create_agent

_agent_singleton: CompiledStateGraph | None = None

def build_agent(checkpointer) -> CompiledStateGraph:
    """构建 agent 单例。free/project 共用，context 在 invoke 时注入。"""
    global _agent_singleton
    if _agent_singleton is not None:
        return _agent_singleton

    _agent_singleton = create_agent(
        model=get_llm(),
        tools=[search_knowledge, quiz_flow],
        middleware=[teaching_prompt],       # @dynamic_prompt 动态 system prompt
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
    return _agent_singleton
```

**为什么单例**：agent 本身无状态（状态在 checkpointer），free/project 差异通过 `context=` 参数在 `astream_events` 时注入，无需多实例。

### 5.7 Runtime（`agent/runtime.py`）

```python
import json
from langchain_core.messages import HumanMessage
from langgraph.types import Command

async def stream_chat(
    agent, session_id: UUID, user_msg: str, context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """首次发送消息 -> SSE 流。"""
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",                # 1.x 流式 API
            context=context,              # 注入 free/project 上下文
        )
        # 1. 流式 token
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        # 2. 检查 interrupt（quiz_flow 触发）
        if stream.interrupted:
            for it in stream.interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return  # session 暂停，不存 agent 消息

        # 3. 流正常结束 -> 存 agent 最终消息
        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("stream_chat failed")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def resume_quiz(
    agent, session_id: UUID, action: str, answer: str | None,
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """提交答题 -> SSE 流继续。"""
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    resume_value = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer

    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),    # 1.x resume API
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


async def _save_final_agent_message(agent, config, db_session, session_id):
    """从 LangGraph state 取最终 AIMessage，存到 Message 表。"""
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if messages:
        final_msg = messages[-1]
        if hasattr(final_msg, "content") and final_msg.content:
            await save_message(db_session, session_id, role="agent", content=final_msg.content)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 5.8 幂等性 Checklist（来自 langgraph-human-in-the-loop skill）

`interrupt()` 之前的代码在 resume 时会**重新执行**。quiz_flow 的幂等模式：

| 步骤 | 首次调用 | Resume 时 |
|---|---|---|
| `get_pending_question(session_id, topic)` | 返回 None | 返回已存的 pending question |
| `_generate_quiz(...)` | 调 LLM 生成 | **跳过**（pending 已存在） |
| `upsert_question(..., status="pending")` | INSERT | ON CONFLICT DO NOTHING（幂等） |
| `interrupt({...})` | raise，暂停 | 返回学生答案 |
| `update_question(...)` | **不执行** | UPDATE 同一行 |

关键：`get_pending_question` + `upsert` 组合保证出题只发生一次。

### 5.9 错误降级策略（MVP 简化版）

| 失败场景 | 降级行为 |
|---|---|
| LightRAG 检索失败 | `search_knowledge` 返回 "知识库检索失败: {e}"，agent 自然处理 |
| 出题 LLM 调用失败 | `quiz_flow` 抛出，被 runtime 捕获，emit `error` SSE 事件 |
| 评估 LLM 调用失败 | 同上 |
| DB 写入失败 | 抛异常，runtime emit `error`，事务回滚 |
| agent 循环超 recursion_limit | LangGraph 抛 `GraphRecursionError`，runtime emit `error` |

**不上 RetryPolicy 中间件**（MVP 简化），LLM 偶发失败由用户重试。

---

## 6. LightRAG 集成

### 6.1 LightRAG 客户端（`lightrag/client.py`）

```python
class LightRAGClient:
    """LightRAG HTTP 客户端，httpx.AsyncClient 连接池复用。"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def start(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=httpx.Timeout(120.0, connect=10.0),  # LLM 调用可能慢
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()

    # === 文档管理（前端代理用） ===
    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self._client.post("/documents/upload", files=files)
        resp.raise_for_status()
        return resp.json()

    async def insert_text(self, body: dict) -> dict: ...
    async def insert_texts(self, body: dict) -> dict: ...
    async def scan(self) -> dict: ...
    async def track_status(self, track_id: str) -> dict: ...
    async def pipeline_status(self) -> dict: ...
    async def status_counts(self) -> dict: ...
    async def list_documents(self, body: dict) -> dict: ...
    async def delete_documents(self, body: dict) -> dict: ...

    # === 查询（agent 内部用，不对前端暴露） ===
    async def query(
        self, query: str, mode: str = "mix",
        only_need_context: bool = False,
        include_references: bool = True,
        **kwargs,
    ) -> dict:
        body = {
            "query": query, "mode": mode,
            "only_need_context": only_need_context,
            "include_references": include_references,
            **kwargs,
        }
        resp = await self._client.post("/query", json=body)
        resp.raise_for_status()
        return resp.json()

    # === 知识图谱（前端代理用） ===
    async def get_graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000) -> dict: ...
    async def list_labels(self) -> list[str]: ...
    async def popular_labels(self, limit: int = 300) -> list[str]: ...
    async def search_labels(self, query: str) -> list[str]: ...

    # === 健康 ===
    async def health(self) -> dict: ...
```

### 6.2 LightRAG 部署信息

- **服务**：`http://101.35.223.219:15434`
- **认证**：`X-API-Key: lightrag-sk-teaching-agent-2026`
- **存储**：全 PostgreSQL（db=`lightrag`）+ NetworkX 图
- **LLM**：DashScope `qwen3.6-flash`（与后端 agent 一致）
- **Embedding**：DashScope `text-embedding-v4`（1024 维）
- **查询模式**：默认 `mix`（KG + 向量，推荐）
- **SUMMARY_LANGUAGE**：Chinese

### 6.3 知识库作用域决策

**单库 + 提示词注入**（已确认）：
- LightRAG 用默认 workspace，所有课程/项目文档都在一个库
- 项目模式 = 项目背景、项目需求被注入到 agent system prompt 中作为引导
- `search_knowledge` 工具调用 LightRAG 时 always 用同一库
- 不实现按项目隔离的多 workspace 管理（YAGNI）

---

## 7. 项目结构

```
教学Agent/
├── teaching_agent_api/                         # 新目录（这一版后端）
│   ├── pyproject.toml                          # uv 项目
│   ├── .env / .env.example
│   ├── .python-version                         # 3.13
│   ├── README.md
│   │
│   ├── src/teaching_agent_api/
│   │   ├── __init__.py
│   │   ├── main.py                             # FastAPI app 装配、lifespan、CORS、路由挂载
│   │   ├── config.py                           # Settings（pydantic-settings）
│   │   ├── deps.py                             # FastAPI 依赖：get_db / get_lightrag_client / get_agent
│   │   │
│   │   ├── api/                                # 路由层（薄）
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                         # POST /chat/sessions/{id}/messages (SSE) + POST /chat/sessions/{id}/quiz/resume (SSE)
│   │   │   ├── sessions.py                     # GET/POST/DELETE /sessions, GET /messages, /questions
│   │   │   ├── projects.py                     # CRUD /projects
│   │   │   ├── documents.py                    # 代理 LightRAG：upload/text/scan/track/list/delete
│   │   │   ├── graph.py                        # 代理 LightRAG：labels/popular/search/graphs
│   │   │   └── health.py                       # GET /health（含 LightRAG 连通性）
│   │   │
│   │   ├── agent/                              # LangGraph agent（5 文件，1.x 最佳实践）
│   │   │   ├── __init__.py
│   │   │   ├── llm.py                          # get_llm() -> ChatOpenAI(qwen3.6-flash, DashScope, enable_thinking=False)
│   │   │   ├── prompts.py                      # GUIDANCE_PROMPT_FREE / GUIDANCE_PROMPT_PROJECT 模板
│   │   │   │                                  # + @dataclass AgentContext(mode, course_name, project_name, project_background_md)
│   │   │   │                                  # + @dynamic_prompt teaching_prompt(request: ModelRequest) -> str
│   │   │   ├── tools.py                        # search_knowledge(query) -> str：调 LightRAG /query only_need_context=True
│   │   │   │                                  # + quiz_flow(topic, config) -> str：含 interrupt() + 幂等出题 + 评估
│   │   │   │                                  # + QuizOutput / EvaluationOutput（Pydantic，with_structured_output 用）
│   │   │   │                                  # + QUIZ_GENERATION_PROMPT / EVALUATION_PROMPT 常量
│   │   │   │                                  # + 模块级 _state 容器（lifespan 注入 LightRAGClient + db_session_factory）
│   │   │   ├── factory.py                     # build_agent(checkpointer) -> create_agent(
│   │   │   │                                  #     model=get_llm(), tools=[search_knowledge, quiz_flow],
│   │   │   │                                  #     middleware=[teaching_prompt], context_schema=AgentContext,
│   │   │   │                                  #     checkpointer=checkpointer)
│   │   │   │                                  # 单例缓存（free/project 共用，context 在 invoke 时注入）
│   │   │   └── runtime.py                     # async stream_chat(session_id, user_msg, context, db_session) -> AsyncIterator[SSEEvent]
│   │   │                                      #   - astream_events(version="v3", context=context)
│   │   │                                      #   - 遍历 stream.messages -> message.text -> emit "text" SSE event
│   │   │                                      #   - stream.interrupted -> emit "quiz_interrupt" + payload，return（不存 agent 消息）
│   │   │                                      #   - 否则存 agent 最终消息 + emit "done"
│   │   │                                      # async resume_quiz(session_id, action, answer, db_session) -> AsyncIterator[SSEEvent]
│   │   │                                      #   - astream_events(Command(resume=...), version="v3")
│   │   │                                      #   - 流式 emit "text"，最后存 agent 最终消息 + emit "done"
│   │   │
│   │   ├── lightrag/                           # LightRAG 客户端封装
│   │   │   ├── __init__.py
│   │   │   ├── client.py                       # LightRAGClient(httpx.AsyncClient) 所有端点方法
│   │   │   └── schemas.py                      # LightRAG 响应 Pydantic 模型：InsertResponse, TrackStatusResponse, PipelineStatusResponse, QueryResponse, QueryDataResponse, GraphData, DocStatusResponse...
│   │   │
│   │   ├── db/                                 # 持久层
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                       # async engine + sessionmaker + lifespan 集成
│   │   │   ├── models.py                       # SQLModel 表：Project, Session, Message, Question
│   │   │   └── repos.py                        # 仓储函数（async）
│   │   │
│   │   └── schemas/                            # API 入参/出参 Pydantic（与 ORM 解耦）
│   │       ├── __init__.py
│   │       ├── chat.py                         # SendMessageRequest, QuizResumeRequest, SSE event schema
│   │       ├── session.py                      # SessionCreate, SessionOut, MessageOut, QuestionOut
│   │       └── project.py                     # ProjectCreate, ProjectUpdate, ProjectOut
│   │
│   └── tests/                                  # 直接打真实 API（不 mock 模型、不 mock LightRAG）
│       ├── conftest.py                         # 真实 DB fixture（teaching-agent-0718）+ 真实 LightRAG fixture
│       ├── test_health.py
│       ├── test_chat_streaming.py              # 真实 qwen3.6-flash 流式 + quiz HITL 全流程
│       ├── test_projects.py
│       ├── test_documents_proxy.py            # 真实调 LightRAG
│       └── test_sessions.py
│
└── docs/superpowers/specs/
    └── 2026-07-19-teaching-agent-api-design.md  # 本设计文档
```

---

## 8. 配置

### 8.1 `.env`

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

### 8.2 `pyproject.toml`

```toml
[project]
name = "teaching-agent-api"
version = "0.1.0"
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
    "asgi-lifespan>=2.1",  # 测试时启动 FastAPI lifespan
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/teaching_agent_api"]
```

### 8.3 运行

```bash
# 安装
cd teaching_agent_api
uv sync

# 配置
cp .env.example .env  # 编辑

# 开发
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000

# 测试（真实 API，不 mock）
uv run pytest tests/ -v
```

---

## 9. 测试策略（不 TDD）

### 9.1 测试原则

- **不 mock 模型**：调真实 DashScope qwen3.6-flash
- **不 mock LightRAG**：调真实 `http://101.35.223.219:15434`
- **不 mock DB**：用真实 `teaching-agent-0718` 数据库（测试前清理测试数据）
- **直接打 API**：用 `httpx.ASGITransport` 直接调 FastAPI app，绕过网络层

### 9.2 测试覆盖

| 测试文件 | 覆盖 |
|---|---|
| `test_health.py` | `/health` 返回所有组件 ok |
| `test_projects.py` | CRUD 全流程；draft/published 状态校验 |
| `test_sessions.py` | 创建（free/project 两种模式）；列表过滤；消息历史；结束会话 |
| `test_documents_proxy.py` | 上传文件 -> 轮询 track_status -> 列表；代理透传正确 |
| `test_chat_streaming.py` | 真实 LLM 流式；quiz HITL 全流程（出题 -> interrupt -> resume -> 评估 -> 后续追问） |

### 9.3 测试 fixture

```python
# conftest.py
@pytest_async.fixture
async def client():
    """真实 ASGI client，绕过网络层"""
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

@pytest_async.fixture
async def cleanup_db():
    """每个测试后清理测试数据"""
    yield
    # 清理：删除所有测试 session/message/question
    ...
```

---

## 10. 未实现 / 未来扩展

| 项 | 说明 |
|---|---|
| 前端 | 下一轮开发，复用 lightrag_webui 技术栈 |
| Alembic 迁移 | schema 稳定后再引入 |
| RetryPolicy 中间件 | LLM 偶发失败率上升后再加 |
| 跨会话学生画像 | 极简版移除，未来用 LangGraph Store 实现 |
| 错题本 + Review 模式 | 极简版移除，未来重新设计 |
| 多 workspace 知识库隔离 | 单库够用后按需引入 |
| 认证 | 极简版无，未来加 JWT/OAuth |
| `quiz_result` SSE 事件 | 极简版走 REST，未来按 UX 需要可加 |
| LangGraph 工具调用事件 | 极简版不暴露 tool_call/tool_result，未来可加 |

---

## 11. 关键风险与对策

| 风险 | 对策 |
|---|---|
| `astream_events(version="v3")` API 可能在 langchain 1.x 不同小版本有差异 | 锁定 `langchain>=1.3,<2.0`；测试覆盖流式 + interrupt |
| `@dynamic_prompt` 中间件 API 不稳定 | 同上；若 API 变化，回退到手搓 StateGraph + prompt 参数 |
| DashScope function calling 偶发不返回 JSON | `with_structured_output(method="function_calling")` + Pydantic 校验 + 异常时工具返回降级字符串 |
| LightRAG `only_need_context=True` 返回格式不明 | 先用默认配置，若 agent 检索质量差，切到 `/query/data` 自行格式化 |
| quiz_flow resume 时幂等性失效 | `get_pending_question` + `upsert_question` 双重保护 |
| agent 陷入循环（连续调 quiz_flow） | `recursion_limit=15` 兜底；prompt 中约束 quiz_flow 使用频率 |

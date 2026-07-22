# Tutoring

Teaching Agent backend: FastAPI 网关 + LangGraph Server（agent 运行时）+ LightRAG + LangChain 1.x。

## Stack

- **Python 3.13** managed by [uv](https://docs.astral.sh/uv/)
- **FastAPI** 网关：鉴权、session CRUD、代理 Server SSE/state
- **LangGraph Server**（`langgraph dev`）托管 agent 运行时（:2024）
- **LightRAG** for retrieval-augmented generation over course materials
- **LangChain 1.x** `create_agent` + tools
- **SQLModel** + **asyncpg** for PostgreSQL access (async)
- **DashScope** (OpenAI-compatible) as the LLM backend

## Layout

```
backend/
├── pyproject.toml
├── langgraph.json            # Server 配置（graph tutor → server_runtime.py:get_graph）
├── .env.example
├── src/tutoring/
│   ├── main.py               # FastAPI app + lifespan（仅 DB）
│   ├── core/                 # 共享内核：config / errors / database / deps / health / lightrag
│   ├── db/                   # 唯一数据真相：models + repos（无业务规则）
│   ├── sessions/             # 会话实体管理：router + service + schemas
│   ├── chat/                 # Server 代理层：proxy（SSE + state 透传）+ server_client（httpx）
│   ├── projects/             # 项目管理：router + service + schemas
│   ├── users/                # 用户管理：router + service + schemas
│   ├── auth/                 # 认证授权：token + bcrypt + role
│   └── agent/                # LangChain agent（零 FastAPI 依赖，由 Server 加载）：factory / tools / prompts / llm / schemas / server_runtime
└── tests/
```

依赖方向单向（DAG）：`core ← 所有模块`；`db ← sessions/chat/projects/users/auth`；
`sessions ← chat/users`；`agent ← core`（仅 Server 侧，FastAPI 进程不导入 agent）。
router/proxy 只调 service / server_client；service 调 repos。chat.proxy 透传 Server
SSE/state，不做事件翻译。

## Setup

```bash
cd backend
cp .env.example .env        # then edit .env if needed
uv sync
```

## Run

两个进程需同时运行：

```bash
# 1. LangGraph Server（agent 运行时，:2024）
uv run langgraph dev --allow-blocking    # --allow-blocking 必须：LightRAG/tiktoken 有同步调用

# 2. FastAPI 网关（:8000）
uv run uvicorn tutoring.main:app --reload --host 0.0.0.0 --port 8000
```

## Health check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "components": {"database": "ok", "langgraph_server": "ok"},
  "versions": {"api": "0.2.0", "langchain": "...", "langgraph": "..."}
}
```

## API

| 端点 | 说明 |
|---|---|
| `POST /auth/login` | 登录，返回 Bearer token |
| `GET/POST /sessions` | 会话 CRUD |
| `GET /threads/{id}/state` | 透传 Server thread state（消息 + interrupts） |
| `POST /threads/{id}/runs/stream` | 透传 Server SSE 流（前端用 `@langchain/langgraph-sdk`） |

前端用 `@langchain/langgraph-sdk` 统一处理流式与历史，`thread_id = session_id`（1:1）。

## Database

Business tables (`project`, `session`, `user`) are created automatically by
`init_db()` at app startup. LangGraph checkpoint tables are managed by the
Server's checkpointer.

Inspect:

```bash
psql "postgresql://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718" -c "\dt"
```

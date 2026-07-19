# Teaching Agent API

Teaching Agent backend built with FastAPI + LightRAG + LangChain 1.x.

## Stack

- **Python 3.13** managed by [uv](https://docs.astral.sh/uv/)
- **FastAPI** for the HTTP API
- **SQLModel** + **asyncpg** for PostgreSQL access (async)
- **LangGraph 1.x** with `AsyncPostgresSaver` for agent state persistence
- **LightRAG** for retrieval-augmented generation over course materials
- **DashScope** (OpenAI-compatible) as the LLM backend

## Layout

```
teaching_agent_api/
├── pyproject.toml
├── .env.example            # template; copy to .env
├── .python-version
└── src/teaching_agent_api/
    ├── main.py             # FastAPI app + lifespan 组装
    ├── core/               # 共享内核：config / errors / database / deps / health
    ├── db/                 # 唯一数据真相：models + repos（无业务规则）
    ├── projects/           # 课程项目域：router + service + schemas
    ├── chat/               # 会话域：router + sse + service + schemas
    ├── knowledge/          # LightRAG 代理：client + router
    ├── agent/              # AI 核心（零 FastAPI 依赖）：factory / runtime / tools / prompts / llm
    └── auth/               # 预留：未来 JWT + role
```

依赖方向单向（DAG）：`core ← 所有模块`；`db ← projects/chat/agent`；
`knowledge ← agent`；`agent ← chat`。router/sse 只调 service；service 调
repos / agent.runtime / knowledge.client。


## Setup

```bash
cd teaching_agent_api
cp .env.example .env        # then edit .env if needed
uv sync
```

## Run

```bash
uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Health check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "components": {"database": "ok", "lightrag": "ok", "agent": "not_built"},
  "versions": {"api": "0.1.0", "langchain": "...", "langgraph": "..."}
}
```

## Database

Business tables (`project`, `session`, `message`, `question`) are created
automatically by `init_db()` at app startup. LangGraph checkpoint tables
(`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) are created by
`AsyncPostgresSaver.setup()`.

Inspect:

```bash
psql "postgresql://root:guoqitong123456@101.35.223.219:15433/teaching-agent-0718" -c "\dt"
```

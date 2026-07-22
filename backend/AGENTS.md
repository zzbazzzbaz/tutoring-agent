# Teaching Agent API

FastAPI 网关 + LangGraph Server（agent 运行时）+ LightRAG + LangChain 1.x 教学 Agent 后端。

## 结构（特性模块 + 共享数据层）

- `core/` 共享内核：config / errors / database / deps / health / lightrag（不依赖任何业务模块）
- `db/` 唯一数据真相：models + repos（纯数据访问，无业务规则）
- `sessions/` 会话实体管理：CRUD + 权限 + 上下文构造（router + service + schemas）
- `chat/` Server 代理层：SSE 流式代理 + state 代理 + server_client（httpx → LangGraph Server）
- `projects/` 项目管理、`users/` 用户管理、`auth/` 认证授权（token + bcrypt + role）
- `agent/` LangChain agent：factory + tools + prompts + schemas（零 FastAPI 依赖，由 LangGraph Server 加载）
- `langgraph.json` Server 配置（graph `tutor` → `agent/server_runtime.py:get_graph`）

## 依赖规则（单向 DAG，禁止反向/循环）

```
core ← 所有模块
db ← sessions / chat / projects / users / auth
sessions ← chat / users          # session 实体共享
agent ← core                      # 仅 Server 侧；FastAPI 进程不导入 agent
```

router / proxy 只调 service / server_client；service 调 repos。
chat.proxy 透传 Server SSE，不做事件翻译。

## 命令

- FastAPI 网关：`uv run uvicorn tutoring.main:app --reload --host 0.0.0.0 --port 8000`
- LangGraph Server：`uv run langgraph dev --allow-blocking`（:2024；`--allow-blocking` 必须：LightRAG/tiktoken 有同步调用）
- 测试：`uv run pytest`（集成测试，需真实 DB + LightRAG + DashScope，见 .env）

## 约定

- 错误：raise `core.errors.AppError(status, code, message)`，对外格式 `{"detail": {"error": {...}}}` 不可变
- 路由依赖 `get_current_user`（CurrentUser.id/.role），不直接读 header
- agent 工具通过 `make_tools(rag=...)` 闭包注入依赖，禁止模块级全局态
- thread_id = session_id（1:1）；SSE / state 原生透传，前端用 `@langchain/langgraph-sdk` 统一渲染流式与历史

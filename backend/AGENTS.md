# Teaching Agent API

FastAPI + LightRAG + LangChain 1.x 教学 Agent 后端。

## 结构（特性模块 + 共享数据层）

- `core/` 共享内核：config / errors / database / deps / health（不依赖任何业务模块）
- `db/` 唯一数据真相：models + repos（纯数据访问，无业务规则）
- `projects/`、`chat/`（含 router+sse+service+schemas）、`knowledge/`（代理透传）、`agent/`（零 FastAPI 依赖）
- `auth/` 预留：未来 JWT + role

## 依赖规则（单向 DAG，禁止反向/循环）

core ← 所有模块；db ← projects/chat/agent；knowledge ← agent；agent ← chat。
router/sse 只调 service；service 调 repos / agent.runtime / knowledge.client。

## 命令

- 运行：`uv run uvicorn tutoring.main:app --reload --host 0.0.0.0 --port 8000`
- 测试：`uv run pytest`（集成测试，需真实 DB + LightRAG + DashScope，见 .env）

## 约定

- 错误：raise `core.errors.AppError(status, code, message)`，对外格式 `{"detail": {"error": {...}}}` 不可变
- 路由依赖 `get_current_user`（CurrentUser.id/.role），不直接读 header
- agent 工具通过 `make_tools()` 闭包注入依赖，禁止模块级全局态

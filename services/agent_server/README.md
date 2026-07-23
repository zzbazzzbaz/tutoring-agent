# Agent Server

基于 LangGraph Server 的教学 Agent 运行时。它负责图执行、工具调用和 LangGraph 资源鉴权；用户、会话与项目权限仍由 API Server 提供。

## 配置

复制 `.env.example` 为 `.env`，至少配置：

- `DASHSCOPE_API_KEY`
- `AGENT_SERVER_SECRET`：必须与 API Server 的同名配置一致。

其余配置均有代码默认值，仅在部署环境不同于本地默认值时设置。LangSmith 与 CORS 配置是可选项。

## 本地运行

```bash
uv sync
uv run langgraph dev
```

运行 API Server 后，Agent Server 会通过 `BACKEND_INTERNAL_URL` 调用 `/auth/internal/agent/authorize` 完成请求授权。

## 校验

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run pytest -q
uv run langgraph validate
```

`langgraph-cli[inmem]` 仅适用于本地开发。生产多副本部署前，需要使用具备共享 checkpoint/store 的 LangGraph 持久化运行时。

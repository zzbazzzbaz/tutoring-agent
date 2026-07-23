# Agent Server

基于 LangGraph Server 的教学 Agent 运行时。它负责图执行、工具调用和 LangGraph 资源鉴权；用户、会话与项目权限仍由 API Server 提供。

## 配置

复制 `.env.example` 为 `.env`，至少配置：

- `DASHSCOPE_API_KEY`
- `AGENT_SERVER_SECRET`：必须与 API Server 的同名配置一致。

其余配置均有代码默认值，仅在部署环境不同于本地默认值时设置。LangSmith 与 CORS 配置是可选项。

## 持久化运行

LangGraph Server 在 PostgreSQL 中自动管理 checkpoint、store、thread 与 run 数据；不要在图代码中注入自定义 checkpointer。

`langgraph up` 会启动 Docker 容器，因此连接宿主机 PostgreSQL 时不能使用 `localhost`。macOS 上请使用 `host.docker.internal`：

```bash
uv sync
uv run langgraph up --postgres-uri "$LANGGRAPH_POSTGRES_URI" --port 2024
```

运行 API Server 后，Agent Server 会通过 `BACKEND_INTERNAL_URL` 调用 `/auth/internal/agent/authorize` 完成请求授权。

`langgraph dev` 仍可用于不需要持久化的快速开发，但它使用 in-memory runtime，不能用于中断恢复或多副本部署验证。

## 校验

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run pytest -q
uv run langgraph validate
```

生产部署时为每个 Agent Server 实例使用同一个 PostgreSQL URI；LangGraph Server 将自动共享 checkpoint/store 状态。

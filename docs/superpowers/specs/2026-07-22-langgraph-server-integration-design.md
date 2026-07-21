# LangGraph Server 托管 AI 服务 — 重构设计

- 日期：2026-07-22
- 范围：`backend/src/tutoring/agent/`、`backend/src/tutoring/chat/`，以及 `main.py` 生命周期与 `core/deps.py` 的相关依赖
- 目标读者：后端开发
- 状态：待评审

## 1. 目标与动机

当前 FastAPI 在进程内「手搓」了 LangGraph agent 的运行时：

- `chat/streaming.py` 用 `asyncio.create_task` + `asyncio.Queue` 驱动 `astream_events`，自管 SSE 流式；
- `chat/tasks.py` 用进程内字典 `_running_tasks` 做同会话并发互斥（409 守卫）与 `processing` 状态；
- `main.py` lifespan 构造 `AsyncPostgresSaver` checkpointer + LightRAG，调 `build_agent` 得到 agent 单例挂在 `app.state.agent`；
- HITL quiz 通过 `present_question` 工具内的 `interrupt()` + `Command(resume=...)` 实现。

这带来两个问题：

1. **并发保护是进程内的**：`_running_tasks` 字典跨进程不可见。多 worker / 多副本部署时，同一 session 的并发请求落到不同进程会穿透守卫，两个 agent run 同时写同一份 LangGraph checkpoint，导致整轮对话丢失、quiz 卡死、resume 错位。
2. **重复造轮子**：手搓的 SSE + 后台任务 + 注册表 + 断线持久化，正是 LangGraph Server 原生提供的能力（`runs/stream` 流式、`multitask_strategy` 跨进程并发控制、`on_disconnect='continue'` 断线持久、托管 checkpointer）。

本次重构把 **agent 运行时交给 LangGraph Server 托管**，FastAPI 退化为「业务网关」：负责 auth、projects、users、sessions 元数据，以及把 chat 相关请求代理给 Server。前端在本次重构后另行适配后端。

## 2. 非目标

- 不改 `auth/`、`projects/`、`users/`、`db/`、`core/`（除生命周期/依赖注入的必要调整）。
- 不引入 `knowledge/` 模块（当前不存在）。
- 不在本 spec 内做前端改造（前端适配后端留作后续独立工作）。
- 不改 LangGraph agent 的业务逻辑（prompts、工具的 `interrupt` 语义、苏格拉底式教学流程保持不变）。
- 不在本 spec 内决定生产部署形态（Cloud vs 自托管规模），仅覆盖开发阶段自托管 `langgraph dev`。

## 3. 目标架构

```
前端 ──HTTP/SSE──> FastAPI (:8000) ──langgraph_sdk──> LangGraph Server (:2024)
                      │                                     │
                 业务 DB（sessions/users/projects）     checkpoint（PG）
                                                      LightRAG（PG+Neo4j，在 graph factory 内）
```

- **FastAPI `:8000`**：鉴权、projects/users/sessions CRUD、chat 网关（代理到 Server）。不再构造 agent、不再自管 checkpointer/rag。
- **LangGraph Server `:2024`**：运行 agent 图（`create_agent` + tools + prompts），托管 checkpointer、流式、HITL interrupt、按 thread 的跨进程并发控制。内网裸跑，不接 auth。
- **thread_id = session_id**：1:1 映射。会话元数据（user/project/title/时间）仍在 FastAPI 的 DB；Server 只存对话状态。
- 前端只与 FastAPI 通信，不直连 Server。

## 4. 模块设计

### 4.1 `agent/` 模块（图定义，跑在 Server 内）

保留：`prompts.py`（`AgentContext` + `main_agent_system_prompt` 中间件）、`tools.py`（`make_tools`：`search_knowledge` + `present_question`，`interrupt()` 语义不变）、`llm.py`（`get_llm`）、`schemas.py`。

**`factory.py` — 解耦 checkpointer**
- 现状：`build_agent(checkpointer, rag)`，checkpointer 由 FastAPI lifespan 传入。
- 改造：`build_agent(*, rag: LightRAG, checkpointer=None)`。Server 要求图**不自带 checkpointer**（它运行时注入），故 Server 路径 `checkpointer=None`。FastAPI 不再调用 `build_agent`。
- `make_tools(rag=rag)` 不变。

**`agent/server_runtime.py` — 新增，Server 入口**
暴露 `langgraph.json` 指向的 graph factory。用 async context manager 模式，仅在真实 run 时初始化重资源（LightRAG），schema 内省时返回轻量 agent：

```python
import contextlib
from langgraph_sdk.runtime import ServerRuntime
from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext
from tutoring.core.lightrag import create_rag

# 内省/Schema 生成用：不连 rag，避免无谓初始化（rag 占位实现见开放问题 11.2）
_introspect_agent = build_agent(rag=<轻量/空 tools agent>)

@contextlib.asynccontextmanager
async def get_graph(runtime: ServerRuntime[AgentContext]):
    if runtime.execution_runtime:           # 真实 run
        rag = create_rag()
        await rag.initialize_storages()
        try:
            yield build_agent(rag=rag)       # checkpointer 由 Server 注入
        finally:
            await rag.finalize_storages()
    else:                                    # Schema/内省
        yield _introspect_agent
```

- `AgentContext`（mode/course_name/project_name/project_background_md）作为 `ServerRuntime[AgentContext]` 的泛型参数；客户端通过 SDK 的 `context={...}` 传入，`@dynamic_prompt` 中间件读 `request.runtime.context`，逻辑不变。

### 4.2 `chat/` 模块（FastAPI 网关）

| 文件 | 处置 | 说明 |
|---|---|---|
| `sessions.py` | 保留 | DB 会话元数据、鉴权（`get_readable/get_writable`）、`build_agent_context`（改为构造传给 Server 的 `context` dict）、`session_to_out_dict`、`touch_session` |
| `router.py` 的 `router`（REST） | 保留 | sessions CRUD + history 端点（history 改调 Server state） |
| `router.py` 的 `sse_router` | 重写 | 两个流式端点改为网关：鉴权 + 校验 + 调 Server SDK `runs.stream` + 转发 SSE |
| `langgraph_client.py` | 新增 | `langgraph_sdk` 薄封装：客户端单例、启动 run 流、resume、取 state、流事件翻译 |
| `history.py` | 重写数据源 | 不再 `agent.aget_state`，改 `client.threads.get_state(thread_id)`；`_extract_items`/`_extract_pending_quiz` 业务逻辑保留 |
| `streaming.py` | 删除 | Server 跑 agent，不再需要 |
| `tasks.py` | 删除 | 并发交给 Server `multitask_strategy='reject'` |
| `schemas.py` | 保留 | 视需要微调 |

**`langgraph_client.py` 职责**
- `get_client() -> AsyncClient`：从配置（`LANGGRAPH_SERVER_URL`，默认 `http://localhost:2024`）构造 SDK 客户端单例。
- `stream_run(thread_id, *, input=None, command=None, context, multitask_strategy)`：调 `client.runs.stream(...)`，把 Server 流事件翻译成网关 SSE 事件（见 §5）。
- `get_thread_state(thread_id)`：`client.threads.get_state(thread_id)`。
- `is_interrupted(thread_id)`：基于 `get_thread_state` 的 `next` 非空判断。
- `has_active_run(thread_id)`：`client.runs.list(thread_id, status="running")` 非空判断（用于 `processing` 标志，见 §6.3）。

**`core/deps.py` 调整**
- 删除 `get_agent(request)`。
- 新增 `get_langgraph_client()`（返回 `langgraph_client.get_client()` 单例，或挂在 `app.state`）。`sse_router` / history 端点依赖它。

**`main.py` 生命周期调整**
- 移除：`AsyncPostgresSaver` 构造、`create_rag()` + `initialize_storages()`、`build_agent`、`app.state.agent`、`app.state.checkpointer`、`app.state.rag`。
- 保留：DB engine + session factory + `init_db`、CORS、LangSmith、各 router 挂载。
- LightRAG 初始化迁移到 `agent/server_runtime.py` 的 factory（Server 侧）。

## 5. SSE 契约（FastAPI -> 前端）

前端后续适配，但为降低改动，**沿用现有 5 个事件名与数据形态**，仅内部数据源从「手搓 astream_events」改为「Server runs.stream 翻译」：

| 事件 | data | 来源（Server 流） |
|---|---|---|
| `text` | `{content: <token>}` | `stream_mode='messages'` 的 token chunk |
| `tool_start` | `{tool_name, tool_input}` | AI 消息的 tool_calls（排除 `present_question`） |
| `quiz_interrupt` | interrupt 的 `value`（quiz 载荷） | `stream_mode='updates'`/`values` 的 `__interrupt__` |
| `done` | `{}` | run 完成 |
| `error` | `{message, code}` | run 失败 / Server 拒绝 |

- `stream_run` 用 `stream_mode=["messages","updates"]`（或 `values`，实现时确认哪种能稳定拿到 `__interrupt__` 与 tool_calls）。
- 翻译逻辑集中在新 `langgraph_client.py`，替换原 `_stream_agent_to_queue` + `_yield_tool_starts`。

## 6. 关键流程

### 6.1 发消息（`POST /chat/sessions/{id}/messages`）
1. `get_writable_session` 鉴权 + 加载会话。
2. `is_interrupted(thread_id)` 为真 -> `409 SESSION_INTERRUPTED`（停在 quiz 必须先 resume）。
3. `touch_session` 更新活跃时间。
4. 构造 `context = build_agent_context(sess)`（mode/course/项目背景）。
5. `StreamingResponse(stream_run(thread_id, input={"messages":[HumanMessage]}, context=context, multitask_strategy="reject", on_disconnect="continue"))` 转发 SSE。
6. Server 若因同 thread 已有 run 在跑而 reject -> 网关捕获映射为 `409 SESSION_PROCESSING`。

### 6.2 恢复 quiz（`POST /chat/sessions/{id}/quiz/resume`）
1. `get_writable_session` 鉴权。
2. `is_interrupted(thread_id)` 为假 -> `409 SESSION_NOT_INTERRUPTED`。
3. 构造 `context`。
4. `StreamingResponse(stream_run(thread_id, command=Command(resume={"action":..., "answer":...}), context=context, multitask_strategy="reject", on_disconnect="continue"))`。
- `Command(resume=...)` 形态与现状完全一致；`present_question` 工具代码不变。

### 6.3 历史（`GET /sessions/{id}/history`）
1. `get_readable_session` 鉴权。
2. `state = get_thread_state(thread_id)`（Server）。
3. `items = _extract_items(state.values.get("messages") or [])`（业务逻辑保留：user/agent/tool_call/quiz item + quiz 状态回填）。
4. `pending_quiz = _extract_pending_quiz(state)`（`state.next` + `tasks.interrupts[].value`）。
5. `processing = has_active_run(thread_id)`（Server runs 查询；若开销/可靠性不理想，可降级为前端据 SSE 连接推断，见 §11.3）。
6. 返回 `{items, pending_quiz, processing}`，结构与现状一致。

### 6.4 并发
- 删除 `_running_tasks` 与 `chat_tasks` 守卫。
- 同 thread 互斥由 Server `multitask_strategy='reject'` 提供，**跨进程安全**，根治原问题。
- 网关把 Server 的 reject 错误映射为 `409 SESSION_PROCESSING`。

### 6.5 断线持久
- 网关调 Server 时带 `on_disconnect='continue'`：前端断开 FastAPI 的 SSE 时，Server 侧 run 继续跑到 done/interrupt，checkpoint 落完整态。前端重连后 `GET /history` 可见完整结果。
- 注：前端断开时 FastAPI 的代理任务被取消，但 Server run 独立于该连接，持久性在 Server 层保证。

## 7. 配置与开发流程

**`backend/langgraph.json`（新增）**
```json
{
  "dependencies": ["."],
  "graphs": { "tutor": "./src/tutoring/agent/server_runtime.py:get_graph" },
  "env": ".env",
  "python_version": "3.13"
}
```
- `dependencies: ["."]` 让 Server 安装本地 `tutoring` 包（读 `pyproject.toml`）。
- `env: ".env"` 复用 DashScope key / DB url / LangSmith。

**`pyproject.toml`**
- 新增 dev 依赖：`langgraph-cli[inmem]`（提供 `langgraph dev`）。
- 新增运行时依赖：`langgraph-sdk`（FastAPI 网关调 Server 用）。

**`core/config.py`**
- 新增 `langgraph_server_url: str = "http://localhost:2024"`。

**开发命令（两个进程并存）**
- Server：`langgraph dev`（:2024，热重载，Studio 自动开）。
- FastAPI：`uv run uvicorn tutoring.main:app --reload --port 8000`。
- 两者共享 `.env`。
- 想要 PG 持久化贴近生产时用 `langgraph up`（Docker + Postgres）。

## 8. 数据模型与 thread 映射
- `session` 表不变（仍绑 user/project/mode/title/时间）。
- `session.id`（UUID）字符串化即 LangGraph `thread_id`，1:1。
- Server 的 thread 不存业务元数据；会话列表/归属仍由 FastAPI DB 提供。

## 9. 迁移策略
一次性重构（big-bang）agent + chat：
1. 改 `factory.build_agent` 解耦 checkpointer；新增 `agent/server_runtime.py` + `langgraph.json`。
2. 新增 `chat/langgraph_client.py`；重写 `chat/history.py` 数据源；重写 `chat/router.py` 的 `sse_router`。
3. 删除 `chat/streaming.py`、`chat/tasks.py`。
4. 调整 `core/deps.py`（`get_agent` -> `get_langgraph_client`）与 `main.py` 生命周期。
5. `langgraph dev` + `uvicorn` 联调跑通发消息 / quiz HITL / 历史。
6. 前端适配留作后续独立工作。

## 10. 测试
- 现有 `tests/test_chat_streaming.py` 走 HTTP 端点，需 Server 在跑。`conftest.py` 需在 fixture 里启动 `langgraph dev`（或对 Server 用测试专用的 in-memory 实例），并保证 FastAPI `langgraph_server_url` 指向它。
- 新增：直接对 Server（Studio / SDK 脚本）验证 `interrupt` + `resume` 全流程、`multitask_strategy='reject'` 的 409 行为。
- `test_sessions.py`（纯 CRUD）不受影响。
- `test_agent_tools.py` 当前因 `tutoring.knowledge` 不存在而无法收集，属预存问题，本 spec 不处理。

## 11. 风险与开放问题

11.1 **`build_agent(checkpointer=None)` 与 Server 注入**：需确认 `create_agent(checkpointer=None)` 在当前 langgraph 版本下，Server 能正确注入 checkpointer 且 `interrupt` 生效。若版本有约束，按其提示处理。

11.2 **内省路径的 rag 占位**：`_introspect_agent` 不能调 `make_tools(rag=真 rag)`（会触发重初始化）。需一个不连 rag 的轻量 agent（`tools=[]` 或 mock rag）。`make_tools` 是否容忍 `rag=None` 待实现时确认；若不容忍，内省路径直接 `create_agent(model, tools=[], middleware=[...], context_schema=AgentContext)`。

11.3 **`processing` 标志的取法**：`has_active_run` 走 Server `runs.list` 增加一次往返。若不稳定或延迟敏感，降级方案：去掉 `processing`，前端据 SSE 连接状态自行推断。

11.4 **Server reject 错误形态**：`multitask_strategy='reject'` 触发时 Server 返回的具体错误码/体需实现时确认，以正确映射为 `409 SESSION_PROCESSING`。

11.5 **`stream_mode` 选择**：`messages` + `updates`/`values` 哪个组合能稳定同时拿到 token、tool_calls、`__interrupt__`，需实现时验证（可能需 `stream_mode=["messages","updates"]`）。

11.6 **LightRAG 生命周期**：factory 每次 run 都 `create_rag` + `initialize_storages` + `finalize`，开销与连接复用需关注；若过重，考虑进程级单例 + 引用计数（实现时评估）。

## 12. 验收标准
- `langgraph dev` 启动后，Studio 能对话、触发 `present_question` interrupt、resume 续跑。
- FastAPI `:8000` 经网关：发消息流式回传 `text/tool_start/done`；quiz 触发 `quiz_interrupt`；resume 后续跑至 `done`。
- `GET /sessions/{id}/history` 返回的 items/pending_quiz 与现状语义一致。
- 同 session 并发发消息：第二个被拒为 `409 SESSION_PROCESSING`（经 Server，跨进程生效）。
- 前端断开 SSE 后，Server run 仍跑完，重连 `GET /history` 可见完整回复。
- `chat/streaming.py`、`chat/tasks.py` 已删除；`main.py` 不再构造 agent/checkpointer/rag。

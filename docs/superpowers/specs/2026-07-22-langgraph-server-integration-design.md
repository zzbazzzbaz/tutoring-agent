# LangGraph Server 托管 AI 服务 - 重构设计

- 日期：2026-07-22
- 范围：`backend/src/tutoring/agent/`、`backend/src/tutoring/chat/`，以及 `main.py` 生命周期与 `core/deps.py` 的相关依赖；前端流式接入
- 目标读者：后端开发
- 状态：待评审

## 1. 目标与动机

当前 FastAPI 在进程内「手搓」了 LangGraph agent 的运行时：

- `chat/streaming.py` 用 `asyncio.create_task` + `asyncio.Queue` 驱动 `astream_events`，自管 SSE 流式；
- `chat/tasks.py` 用进程内字典 `_running_tasks` 做同会话并发互斥（409 守卫）与 `processing` 状态；
- `main.py` lifespan 构造 `AsyncPostgresSaver` checkpointer + LightRAG，调 `build_agent` 得到 agent 单例挂在 `app.state.agent`；
- HITL quiz 通过 `present_question` 工具内的 `interrupt()` + `Command(resume=...)` 实现。

两个问题：

1. **并发保护是进程内的**：`_running_tasks` 字典跨进程不可见。多 worker / 多副本时同一 session 的并发请求落到不同进程会穿透守卫，两个 run 同时写同一份 checkpoint，导致整轮对话丢失、quiz 卡死、resume 错位。
2. **重复造轮子**：手搓的 SSE + 后台任务 + 注册表 + 断线持久 + 事件翻译，正是 LangGraph Server 原生能力（`runs/stream` 流式、`multitask_strategy` 跨进程并发、`on_disconnect='continue'` 断线持久、托管 checkpointer、标准流事件协议）。

本次重构把 **agent 运行时交给 LangGraph Server 托管**，FastAPI 退化为「业务网关 + Server 协议代理」。**网关伪装成 Server 的流式端点**（`/threads/{thread_id}/runs/stream`），前端用官方 `@langchain/langgraph-sdk` 接住 SSE；流式事件**原样透传**，不在网关翻译。鉴权 / session→context 映射 / 历史重建等领域逻辑留在网关。

## 2. 非目标

- 不改 `auth/`、`projects/`、`users/`、`db/`、`core/`（除生命周期/依赖注入的必要调整）。
- 不引入 `knowledge/` 模块（当前不存在）。
- 不改 LangGraph agent 的业务逻辑（prompts、工具的 `interrupt` 语义、苏格拉底式教学流程不变）。
- 不在本 spec 内决定生产部署形态，仅覆盖开发阶段自托管 `langgraph dev`。
- 前端 sessions CRUD / history 仍用普通 fetch（不走 SDK）；SDK 仅用于流式 + resume。

## 3. 目标架构

```
前端 ──SDK runs.stream──> FastAPI (:8000) ──httpx 透传──> LangGraph Server (:2024)
      ──fetch /sessions/*──>  FastAPI                         │
      ──fetch /sessions/{id}/history──> FastAPI          checkpoint（PG）
              │                                            LightRAG（PG+Neo4j，graph factory 内）
         业务 DB（sessions/users/projects）
```

- **FastAPI `:8000`**：
  - `POST /threads/{thread_id}/runs/stream`（**新增，伪装 Server**）：鉴权 + 加载 session + 拼 AgentContext + 注入并发/断线参数 + is_interrupted 守卫 + httpx 透传 Server 的 SSE（+ 心跳多路复用）。前端 SDK 直接打这里。
  - `/sessions/*` REST（保留）：sessions CRUD。
  - `GET /sessions/{id}/history`（保留，重写数据源）：网关取 Server state 后跑 `_extract_items` 还原 item。
  - 不再构造 agent / checkpointer / rag。
- **LangGraph Server `:2024`**：运行 agent 图，托管 checkpointer / 流式 / HITL interrupt / 按 thread 跨进程并发。内网裸跑，不接 auth。
- **thread_id = session_id**（1:1）：会话元数据在 FastAPI DB；Server 只存对话状态。
- **前端**：流式 + resume 用 `@langchain/langgraph-sdk` 指向 FastAPI；sessions / history 用普通 fetch。不直连 Server。

## 4. 模块设计

### 4.1 `agent/` 模块（图定义，跑在 Server 内）

保留：`prompts.py`（`AgentContext` + `main_agent_system_prompt`）、`tools.py`（`make_tools`：`search_knowledge` + `present_question`，`interrupt()` 不变）、`llm.py`、`schemas.py`。

**`factory.py` - 解耦 checkpointer**
- 改造：`build_agent(*, rag: LightRAG, checkpointer=None)`。Server 要求图**不自带 checkpointer**（运行时注入）。FastAPI 不再调用 `build_agent`。
- `make_tools(rag=rag)` 不变。

**`agent/server_runtime.py` - 新增，Server 入口**
`langgraph.json` 指向的 graph factory，async context manager，仅真实 run 时初始化 LightRAG：

```python
import contextlib
from langgraph_sdk.runtime import ServerRuntime
from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext
from tutoring.core.lightrag import create_rag

# 内省/Schema 用：不连 rag（占位实现见开放问题 11.2）
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

- `AgentContext` 作为 `ServerRuntime[AgentContext]` 泛型参数；客户端经 SDK `context={...}` 传入，`@dynamic_prompt` 读 `request.runtime.context`，不变。

### 4.2 `chat/` 模块（FastAPI 网关）

| 文件 | 处置 | 说明 |
|---|---|---|
| `sessions.py` | 保留 | 鉴权（`get_readable/get_writable`）、`build_agent_context`（构造 Server `context`）、`session_to_out_dict`、`touch_session` |
| `router.py` 的 `router`（REST） | 保留 | sessions CRUD + history 端点 |
| `proxy.py` | 新增 | `APIRouter()` 暴露 `POST /threads/{thread_id}/runs/stream`：鉴权 + 拼 context + 注入参数 + 守卫 + httpx 透传 SSE + 心跳 |
| `server_client.py` | 新增 | httpx 封装：`proxy_run_stream()`（透传 + 心跳多路复用）、`get_state(thread_id)`、`is_interrupted(thread_id)`、`has_active_run(thread_id)` |
| `history.py` | 重写数据源 | 不再 `agent.aget_state`，改 `server_client.get_state`；`_extract_items`/`_extract_pending_quiz` 业务逻辑保留 |
| `streaming.py` | 删除 | Server 跑 agent |
| `tasks.py` | 删除 | 并发交给 Server `multitask_strategy='reject'` |
| `router.py` 的 `sse_router` | 删除 | 流式改由 `proxy.py` 伪装 Server 路由承担 |
| `schemas.py` | 保留 | 视需要微调 |

**`proxy.py` - 伪装 Server 流式端点**
`POST /threads/{thread_id}/runs/stream`：
1. `get_writable_session(db, thread_id, user)`（thread_id 即 session_id）鉴权 + 加载会话。
2. 解析前端 SDK 请求体：保留 `input`/`command`/`stream_mode`；**注入** `assistant_id="tutor"`、`context=build_agent_context(sess)`、`multitask_strategy="reject"`、`on_disconnect="continue"`、`if_not_exists="create"`。
3. 守卫：`input` 在且 `is_interrupted` -> `409 SESSION_INTERRUPTED`；`command` 在且非 `is_interrupted` -> `409 SESSION_NOT_INTERRUPTED`。
4. `input` 在时 `touch_session`（更新活跃时间；resume 不 touch，保持现状）。
5. `StreamingResponse(server_client.proxy_run_stream(thread_id, body))`：httpx POST 到 Server 同名路由，原样透传 SSE 字节，叠加 15s 心跳。

**`server_client.py` 职责**
- `proxy_run_stream(thread_id, body)`：`httpx.AsyncClient.stream("POST", f"{server_url}/threads/{thread_id}/runs/stream", json=body)`，`async for chunk in resp.aiter_bytes(): yield chunk`；与一个 15s 发 `b": heartbeat\n\n"` 的并发任务多路复用合并 yield。
- `get_state(thread_id)`：httpx GET `{server_url}/threads/{thread_id}/state`，返回 JSON。
- `is_interrupted(thread_id)`：基于 `get_state` 的 `next` 非空。
- `has_active_run(thread_id)`：httpx GET `{server_url}/threads/{thread_id}/runs?status=running` 非空（用于 `processing`，见 §6.3/§11.3）。
- 网关**不依赖 Python `langgraph-sdk`**（透传用 httpx；`Command(resume=...)` 由前端 SDK 构造、原样透传，网关不构造）。

**`core/deps.py` 调整**
- 删除 `get_agent(request)`。
- `get_db` / `get_current_user` 保留；`proxy.py` / history 端点用现有依赖即可（无需新依赖注入）。

**`main.py` 生命周期调整**
- 移除：`AsyncPostgresSaver`、`create_rag()`+`initialize_storages()`、`build_agent`、`app.state.agent/checkpointer/rag`。
- 保留：DB engine + session factory + `init_db`、CORS、LangSmith、router 挂载。
- 挂载 `chat.router.router`（REST）+ `chat.proxy.router`（流式代理）；移除原 `sse_router` 挂载。
- LightRAG 初始化迁移到 `agent/server_runtime.py`（Server 侧）。

## 5. SSE 契约（FastAPI -> 前端）

**透传 Server 原生事件，不翻译。** 前端用 `@langchain/langgraph-sdk` 解析。网关只做字节透传 + 心跳：

- 前端 SDK 调 `client.runs.stream(threadId, "tutor", { input|command, stream_mode: ["messages","updates"] })`。
- Server 原生事件类型（`metadata` / `messages/partial` / `messages/complete` / `updates` / `values` / `end` / `error` 等）原样转发；token、tool_calls、`__interrupt__`（quiz 载荷）均由 SDK 原生处理。
- 网关额外注入 15s `: heartbeat`（LLM 沉默时保活），与 Server 事件流多路复用。
- 不再有自定义 `text/tool_start/quiz_interrupt/done/error` 5 事件；这些语义由 SDK 在前端侧还原。

## 6. 关键流程

### 6.1 发消息（前端 SDK `runs.stream` with `input`）
1. 前端 SDK POST `/threads/{session_id}/runs/stream`，body 含 `input={"messages":[...]}`、`stream_mode`。
2. 网关 `get_writable_session` 鉴权；注入 `assistant_id/context/multitask_strategy="reject"/on_disconnect="continue"/if_not_exists="create"`。
3. `is_interrupted` 为真 -> `409 SESSION_INTERRUPTED`。
4. `touch_session`。
5. httpx 透传到 Server，SSE 原样回传 + 心跳。
6. Server 因同 thread 已有 run 在跑而 reject -> 透传其错误（网关可映射为 `409 SESSION_PROCESSING`，见 §11.4）。

### 6.2 恢复 quiz（前端 SDK `runs.stream` with `command`）
1. 前端 SDK POST，body 含 `command=Command(resume={"action":..., "answer":...})`。
2. 网关鉴权 + 注入参数。
3. `is_interrupted` 为假 -> `409 SESSION_NOT_INTERRUPTED`。
4. httpx 透传；`Command(resume=...)` 形态与现状一致，`present_question` 工具不变。

### 6.3 历史（`GET /sessions/{id}/history`，普通 fetch）
1. `get_readable_session` 鉴权。
2. `state = server_client.get_state(thread_id)`。
3. `items = _extract_items(state["values"]["messages"])`（业务逻辑保留）。
4. `pending_quiz = _extract_pending_quiz(state)`（`next` + `tasks.interrupts[].value`）。
5. `processing = has_active_run(thread_id)`（可降级，见 §11.3）。
6. 返回 `{items, pending_quiz, processing}`，结构与现状一致。

### 6.4 并发
- 删除 `_running_tasks` / `chat_tasks`。
- 同 thread 互斥由 Server `multitask_strategy='reject'` 提供，**跨进程安全**。
- 网关保留 `is_interrupted` 守卫，给出 app 语义化的 `409 SESSION_INTERRUPTED/NOT_INTERRUPTED`；Server reject 映射为 `409 SESSION_PROCESSING`。

### 6.5 断线持久
- 网关带 `on_disconnect='continue'` 调 Server：前端断开 FastAPI 的 SSE 时，Server 侧 run 继续跑到 done/interrupt，checkpoint 落完整态。前端重连 `GET /history` 可见完整结果。
- 注：前端断开时 FastAPI 的 httpx 透传任务被取消，但 Server run 独立于该连接，持久性在 Server 层保证。

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

**`pyproject.toml`**
- 运行时依赖新增：`langgraph-sdk`（`agent/server_runtime.py` 的 `ServerRuntime` 用，随 `tutoring` 包装进 Server）。
- dev 依赖新增：`langgraph-cli[inmem]`（`langgraph dev`）。
- 运行时依赖新增：`langgraph-sdk`（`agent/server_runtime.py` 的 `ServerRuntime` 用）。`httpx` 已是运行时依赖，网关透传直接复用。
- 前端新增依赖：`@langchain/langgraph-sdk`。

**`core/config.py`**
- 新增 `langgraph_server_url: str = "http://localhost:2024"`。

**开发命令（两进程并存，共享 `.env`）**
- Server：`langgraph dev`（:2024，热重载，Studio 自动开）。
- FastAPI：`uv run uvicorn tutoring.main:app --reload --port 8000`。
- 想要 PG 持久化贴近生产时用 `langgraph up`（Docker + Postgres）。

## 8. 数据模型与 thread 映射
- `session` 表不变（绑 user/project/mode/title/时间）。
- `session.id` 字符串化即 LangGraph `thread_id`，1:1。
- Server thread 不存业务元数据；会话列表/归属仍由 FastAPI DB 提供。

## 9. 迁移策略
一次性重构（big-bang）agent + chat：
1. `factory.build_agent` 解耦 checkpointer；新增 `agent/server_runtime.py` + `langgraph.json`。
2. 新增 `chat/server_client.py`（httpx）+ `chat/proxy.py`（伪装 `/threads/{id}/runs/stream`）；重写 `chat/history.py` 数据源。
3. 删除 `chat/streaming.py`、`chat/tasks.py`、`router.py` 的 `sse_router`。
4. 调整 `main.py` 生命周期 + router 挂载；`core/deps.py` 删 `get_agent`。
5. `langgraph dev` + `uvicorn` 联调跑通发消息 / quiz HITL / 历史。
6. 前端接入 `@langchain/langgraph-sdk`（流式/resume）+ 保留 sessions/history fetch。

## 10. 测试
- `tests/test_chat_streaming.py` 走 `/threads/{id}/runs/stream`（经 SDK 或直接 POST），需 Server 在跑。`conftest.py` 需在 fixture 启动 `langgraph dev`（或测试专用 in-memory Server），并让 `langgraph_server_url` 指向它。
- 新增：直接对 Server（Studio / SDK 脚本）验证 `interrupt`+`resume`、`multitask_strategy='reject'` 的 409。
- `test_sessions.py`（纯 CRUD）不受影响。
- `test_agent_tools.py` 因 `tutoring.knowledge` 不存在无法收集，预存问题，不处理。

## 11. 风险与开放问题

11.1 **`build_agent(checkpointer=None)` 与 Server 注入**：确认 `create_agent(checkpointer=None)` 下 Server 能注入 checkpointer 且 `interrupt` 生效。

11.2 **内省路径 rag 占位**：`_introspect_agent` 不能连真 rag。`make_tools(rag=None)` 是否容忍待确认；若不容忍，内省路径直接 `create_agent(model, tools=[], middleware=[...], context_schema=AgentContext)`。

11.3 **`processing` 取法**：`has_active_run` 走 Server `runs?status=running` 增一次往返；若不稳定/延迟敏感，降级为去掉 `processing`，前端据 SSE 连接推断。

11.4 **Server reject 错误形态 / 路由对齐**：`multitask_strategy='reject'` 的错误码/体需确认以映射 `409 SESSION_PROCESSING`；**需核对 JS SDK `runs.stream` 的实际 HTTP 路由**（`/threads/{id}/runs/stream` vs `/runs/stream?thread_id=`）与请求体字段，网关据此精确伪装。若 SDK 还调用别的端点（如 `threads.create`），评估是否需额外伪装或改用普通 fetch。

11.5 **`stream_mode` 选择**：`["messages","updates"]` 能否稳定同时拿到 token、tool_calls、`__interrupt__`，实现时验证。

11.6 **心跳与透传合并**：httpx 流式 `aiter_bytes` + 并发心跳任务的多路复用实现需注意背压与取消语义。

11.7 **LightRAG 生命周期**：factory 每 run `create_rag`+`initialize`+`finalize`，开销/连接复用需评估；过重则进程级单例 + 引用计数。

## 12. 验收标准
- `langgraph dev` 启动后，Studio 能对话、触发 `present_question` interrupt、resume 续跑。
- 前端经 `@langchain/langgraph-sdk` 打 FastAPI `/threads/{id}/runs/stream`：发消息流式收到原生 token 事件；quiz 触发 `__interrupt__`；`command=Command(resume=...)` 后续跑至 `end`。
- `GET /sessions/{id}/history` 返回的 items/pending_quiz 与现状语义一致。
- 同 session 并发发消息：第二个被拒为 `409 SESSION_PROCESSING`（经 Server，跨进程生效）。
- 前端断开 SSE 后，Server run 仍跑完，重连 `GET /history` 可见完整回复。
- `chat/streaming.py`、`chat/tasks.py`、`sse_router` 已删除；`main.py` 不再构造 agent/checkpointer/rag。
- 网关**不翻译** SSE 事件，原生透传 + 心跳。

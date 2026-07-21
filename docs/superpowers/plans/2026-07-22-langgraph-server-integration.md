# LangGraph Server 托管 AI 服务 - 实现计划（后端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 agent 运行时交给 LangGraph Server 托管，FastAPI 退化为业务网关 + Server 协议代理（`/threads/{id}/runs/stream` 透传原生 SSE），删除手搓的 streaming/tasks 层。

**Architecture:** FastAPI `:8000` 伪装 Server 流式端点（鉴权 + 拼 context + 注入并发/断线参数 + is_interrupted 守卫 + httpx 透传 SSE + 心跳）；LangGraph Server `:2024` 跑 agent 图、托管 checkpointer/HITL/并发。`thread_id = session_id`。history 由网关取 Server state 后用 `messages_from_dict` 还原成 item。前端用 `@langchain/langgraph-sdk` 接 SSE（前端适配留作后续独立计划）。

**Tech Stack:** FastAPI, langgraph (lib) + langgraph-sdk + langgraph-cli[inmem], httpx, langchain_core, LightRAG, pytest (asyncio_mode=auto)

## Global Constraints

- Python >=3.13；包管理用 `uv`。
- `thread_id` 恒等于 `session.id` 字符串化（1:1）。
- 网关**不依赖 Python `langgraph-sdk`** 做流式消费（用 httpx 透传字节）；`langgraph-sdk` 仅 `agent/server_runtime.py` 的 `ServerRuntime` 用。
- 网关**不翻译** SSE 事件，原生透传 + 15s 心跳。
- 错误用 `core.errors.AppError(status, code, message)`，对外体 `{"detail":{"error":{...}}}` 不变。
- agent 业务逻辑（prompts、`present_question` 的 `interrupt()`、苏格拉底流程）不变。
- 集成测试需真实服务：Postgres + DashScope + LightRAG，**外加 `langgraph dev` 在跑**（见各 Task 前置）。
- 命令默认在 `backend/` 目录执行（除非另注）。

## File Structure

**新建：**
- `backend/langgraph.json` — Server 配置（graphs/dependencies/env）
- `backend/src/tutoring/agent/server_runtime.py` — graph factory（`get_graph` async ctx manager）
- `backend/src/tutoring/chat/server_client.py` — httpx 封装：`get_state`/`is_interrupted`/`has_active_run`/`proxy_run_stream` + 纯函数 `state_is_interrupted`
- `backend/src/tutoring/chat/proxy.py` — `APIRouter` 暴露 `POST /threads/{thread_id}/runs/stream`
- `backend/tests/test_history_extract.py` — `_extract_items`/`_extract_pending_quiz` 纯逻辑单测
- `backend/tests/test_server_client.py` — `state_is_interrupted` 纯逻辑单测 + `get_state` 集成

**修改：**
- `backend/src/tutoring/agent/factory.py` — `build_agent(*, rag, checkpointer=None)`
- `backend/src/tutoring/chat/history.py` — 数据源改 `server_client.get_state` + `messages_from_dict` 转换；`_extract_pending_quiz` 适配 dict state；`build_history(thread_id)`
- `backend/src/tutoring/chat/sessions.py` — `build_agent_context` 返回 dict
- `backend/src/tutoring/chat/router.py` — `get_history` 去 agent 依赖、调新 `build_history(thread_id)`
- `backend/src/tutoring/main.py` — lifespan 去 agent/checkpointer/rag；挂 `proxy.router`；去 `sse_router`
- `backend/src/tutoring/core/deps.py` — 删 `get_agent`
- `backend/src/tutoring/core/config.py` — 加 `langgraph_server_url`
- `backend/pyproject.toml` — 加 `langgraph-sdk`（运行时）、`langgraph-cli[inmem]`（dev）
- `backend/tests/conftest.py` — 集成测试前置说明（Server 在跑）

**删除：**
- `backend/src/tutoring/chat/streaming.py`
- `backend/src/tutoring/chat/tasks.py`
- `backend/src/tutoring/chat/sse.py`（其 `sse_router` 由 `proxy.py` 取代）

---

### Task 1: 解耦 build_agent + Server 脚手架 + 验证 `langgraph dev`

**前置：** `.env` 已配置 DashScope key / database_url（现有）。

**Files:**
- Modify: `backend/src/tutoring/agent/factory.py`
- Create: `backend/langgraph.json`
- Create: `backend/src/tutoring/agent/server_runtime.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: `build_agent(*, rag: LightRAG, checkpointer=None) -> CompiledStateGraph`；`get_graph(runtime: ServerRuntime[AgentContext])` async context manager；`langgraph.json` graph id `"tutor"`。

- [ ] **Step 1: 改 `factory.py` 解耦 checkpointer**

```python
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from lightrag import LightRAG

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import AgentContext, main_agent_system_prompt
from tutoring.agent.tools import make_tools


def build_agent(*, rag: LightRAG, checkpointer=None) -> CompiledStateGraph:
    """构建 agent。Server 路径不传 checkpointer（Server 运行时注入）。

    Args:
        rag: LightRAG SDK 实例（知识库查询）
        checkpointer: 仅遗留路径用；Server 托管时为 None

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    tools = make_tools(rag=rag)
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 2: 加依赖到 `pyproject.toml`**

在 `dependencies` 列表 LangGraph 生态段加：
```toml
    "langgraph-sdk>=0.1",
```
在 `[dependency-groups] dev` 加：
```toml
    "langgraph-cli[inmem]>=0.1",
```

- [ ] **Step 3: 同步依赖**

Run: `uv sync`
Expected: 安装 `langgraph-sdk`、`langgraph-cli[inmem]` 成功。

- [ ] **Step 4: 创建 `backend/langgraph.json`**

```json
{
  "dependencies": ["."],
  "graphs": { "tutor": "./src/tutoring/agent/server_runtime.py:get_graph" },
  "env": ".env",
  "python_version": "3.13"
}
```

- [ ] **Step 5: 创建 `agent/server_runtime.py`**

```python
"""LangGraph Server 入口：graph factory。

仅真实 run 时初始化 LightRAG（重资源），schema 内省时返回不连 rag 的轻量 agent。
checkpointer 由 Server 运行时注入，这里不传。
"""
import contextlib

from langgraph_sdk.runtime import ServerRuntime

from tutoring.agent.factory import build_agent
from tutoring.agent.prompts import AgentContext
from tutoring.core.lightrag import create_rag


def _build_introspect_agent():
    """内省/schema 用：不连 rag（见开放问题，make_tools 容忍 rag=None 时用真 build_agent）。

    若 make_tools 不容忍 rag=None，直接构造无工具 agent：
    """
    from langchain.agents import create_agent
    from tutoring.agent.llm import get_llm
    from tutoring.agent.prompts import main_agent_system_prompt
    return create_agent(
        model=get_llm(),
        tools=[],
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
    )


_introspect_agent = _build_introspect_agent()


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

- [ ] **Step 6: 验证 Server 启动 + graph 加载**

Run: `langgraph dev`（在 `backend/` 目录）
Expected: Server 在 `http://localhost:2024` 起来；浏览器开 LangGraph Studio；assistant/graph `tutor` 可见；**无导入错误**。若报 `make_tools(rag=None)` 相关错误，确认 Step 5 走的是无工具内省分支（已规避）。

- [ ] **Step 7: 验证 interrupt + checkpointer 注入（开放问题 11.1）**

在 Studio 里对 `tutor` 发「请用 present_question 考考我 HTTP」：
Expected: agent 调 `present_question` -> 图暂停（interrupt）-> Studio 显示 interrupt value（quiz 载荷）。在 Studio 输入答案 resume -> agent 续跑。
**记录结论**：checkpointer 是否由 Server 正确注入、interrupt 是否生效。若不生效，检查 `build_agent(checkpointer=None)` 是否被 Server 接受（可能需省略 checkpicker 参数）。

- [ ] **Step 8: 验证 SDK 路由形态（开放问题 11.4）**

另开终端，用 Python SDK 探测 `runs.stream` 的实际 HTTP 路由：

```python
# scripts/probe_route.py（临时脚本，验证后可删）
import asyncio
from langgraph_sdk import get_client

async def main():
    async with get_client(url="http://localhost:2024") as c:
        try:
            async for chunk in c.runs.stream(
                thread_id=None, assistant_id="tutor",
                input={"messages": [{"role": "user", "content": "你好"}]},
                stream_mode=["messages", "updates"],
            ):
                print(type(chunk).__name__, str(chunk)[:120])
                break
        except Exception as e:
            print("ERR", e)

asyncio.run(main())
```

Run: `uv run python scripts/probe_route.py`
Expected: 打印首个 chunk 类型（如 `metadata`/`messages/partial`）。**记录结论**：SDK 实际 POST 的路由（用抓包或 Server 日志确认是 `/threads/{id}/runs/stream` 还是 `/runs/stream?thread_id=`）与 `stream_mode` 事件类型。此结论决定 Task 5 的 `proxy.py` 路由与 Task 4 的透传目标 URL。

- [ ] **Step 9: 提交**

```bash
git add backend/src/tutoring/agent/factory.py backend/src/tutoring/agent/server_runtime.py backend/langgraph.json backend/pyproject.toml backend/uv.lock
git commit -m "feat(agent): 解耦 checkpointer + server_runtime factory + langgraph.json，跑通 langgraph dev"
```

---

### Task 2: config + server_client 基础（get_state / state_is_interrupted / is_interrupted / has_active_run）

**前置：** Task 1 完成；`langgraph dev` 可运行（集成测试步骤需要）。

**Files:**
- Modify: `backend/src/tutoring/core/config.py`
- Create: `backend/src/tutoring/chat/server_client.py`
- Test: `backend/tests/test_server_client.py`

**Interfaces:**
- Produces: `server_client.get_state(thread_id: str) -> dict`；`server_client.state_is_interrupted(state: dict) -> bool`（纯函数）；`server_client.is_interrupted(thread_id: str) -> bool`；`server_client.has_active_run(thread_id: str) -> bool`。Task 3/5 依赖这些。

- [ ] **Step 1: 写 `state_is_interrupted` 失败测试**

`backend/tests/test_server_client.py`：
```python
from tutoring.chat.server_client import state_is_interrupted


def test_state_is_interrupted_true_when_next_nonempty():
    assert state_is_interrupted({"next": ["__interrupt__"], "values": {}, "tasks": []}) is True


def test_state_is_interrupted_false_when_next_empty():
    assert state_is_interrupted({"next": [], "values": {}, "tasks": []}) is False


def test_state_is_interrupted_false_when_missing_next():
    assert state_is_interrupted({"values": {}}) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_server_client.py -v`
Expected: FAIL（`ModuleNotFoundError: tutoring.chat.server_client`）。

- [ ] **Step 3: 加 config**

`backend/src/tutoring/core/config.py` 在 `Settings` 类内加：
```python
    # LangGraph Server
    langgraph_server_url: str = "http://localhost:2024"
```

- [ ] **Step 4: 写 `server_client.py` 基础部分**

```python
"""LangGraph Server 的 httpx 客户端（网关侧）。

透传流式用 httpx（不依赖 Python langgraph-sdk 消费）；state 查询也用 httpx。
"""
import httpx

from tutoring.core.config import settings


def _base() -> str:
    return settings.langgraph_server_url.rstrip("/")


def state_is_interrupted(state: dict) -> bool:
    """纯函数：state 的 next 非空表示停在 interrupt。"""
    return bool(state.get("next"))


async def get_state(thread_id: str) -> dict:
    """GET /threads/{thread_id}/state，返回 state JSON。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_base()}/threads/{thread_id}/state")
        resp.raise_for_status()
        return resp.json()


async def is_interrupted(thread_id: str) -> bool:
    """会话是否停在 interrupt（有未答 quiz）。"""
    try:
        return state_is_interrupted(await get_state(thread_id))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False  # thread 尚未创建（首次发消息），视为未中断
        raise


async def has_active_run(thread_id: str) -> bool:
    """是否有正在运行的 run（用于 history 的 processing 标志）。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_base()}/threads/{thread_id}/runs", params={"status": "running"}
        )
        resp.raise_for_status()
        return bool(resp.json())
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_server_client.py -v`
Expected: 3 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/src/tutoring/core/config.py backend/src/tutoring/chat/server_client.py backend/tests/test_server_client.py
git commit -m "feat(chat): server_client get_state/is_interrupted + langgraph_server_url 配置"
```

---

### Task 3: history.py 重写（Server state 数据源 + messages_from_dict）

**前置：** Task 2 完成。

**Files:**
- Modify: `backend/src/tutoring/chat/history.py`
- Modify: `backend/src/tutoring/chat/router.py`（`get_history` 去 agent 依赖）
- Test: `backend/tests/test_history_extract.py`

**Interfaces:**
- Consumes: `server_client.get_state`、`server_client.has_active_run`、`server_client.state_is_interrupted`
- Produces: `history.build_history(thread_id: str) -> dict`（返回 `{items, pending_quiz, processing}`，结构不变）。`router.get_history` 改调它。

**说明：** Server state API 返回 JSON dict（messages 是序列化 dict 列表，非 BaseMessage 对象）。用 `langchain_core.messages.messages_from_dict` 转回对象后复用 `_extract_items`。`_extract_pending_quiz` 改适配 dict state。`iter_tool_calls` 从 `streaming.py` 复制进来（streaming 在 Task 6 删除，临时重复，删除后消除）。

- [ ] **Step 1: 写 `_extract_items` 纯逻辑测试**

`backend/tests/test_history_extract.py`：
```python
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tutoring.chat.history import _extract_items, _extract_pending_quiz


def test_extract_items_user_and_agent():
    msgs = [HumanMessage(content="你好"), AIMessage(content="你好呀")]
    items = _extract_items(msgs)
    assert items == [
        {"type": "user", "content": "你好"},
        {"type": "agent", "content": "你好呀"},
    ]


def test_extract_pending_quiz_none_when_no_next():
    assert _extract_pending_quiz({"next": [], "tasks": []}) is None


def test_extract_pending_quiz_returns_value():
    state = {"next": ["x"], "tasks": [{"interrupts": [{"value": {"stem": "q?"}}]}]}
    assert _extract_pending_quiz(state) == {"stem": "q?"}
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_history_extract.py -v`
Expected: FAIL（`_extract_pending_quiz` 对 dict 返回 None / 旧实现按属性取值）。

- [ ] **Step 3: 重写 `history.py`**

```python
"""会话历史重建（读侧）。

数据源从 LangGraph Server 的 threads/state API 取（JSON），用 messages_from_dict
转回消息对象后复用 _extract_items 还原成前端 item 列表。
"""
import inspect
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_from_dict

from tutoring.chat import server_client


async def build_history(thread_id: str) -> dict:
    """重建会话历史：item 列表 + pending_quiz + processing 标志。"""
    state = await server_client.get_state(thread_id)
    raw_msgs = (state.get("values") or {}).get("messages") or []
    messages = messages_from_dict(raw_msgs)

    items = _extract_items(messages)
    pending_quiz = _extract_pending_quiz(state)
    processing = await server_client.has_active_run(thread_id)

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}


# === item 提取 ===


def _extract_items(messages: list) -> list[dict]:
    """把消息序列还原成前端 item 列表（逻辑不变）。"""
    items: list[dict] = []
    pending_quizzes: list[int] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            _collect_human_message(msg, items)
        elif isinstance(msg, AIMessage):
            _collect_ai_message(msg, items, pending_quizzes)
        elif isinstance(msg, ToolMessage):
            _apply_tool_result(msg, items, pending_quizzes)

    return items


def _collect_human_message(msg: HumanMessage, items: list[dict]) -> None:
    if msg.text:
        items.append({"type": "user", "content": msg.text})


def _collect_ai_message(msg: AIMessage, items: list[dict], pending_quizzes: list[int]) -> None:
    for name, args in _iter_tool_calls(msg):
        if name == "present_question":
            items.append(_build_quiz_item(args))
            pending_quizzes.append(len(items) - 1)
        elif name:
            items.append({"type": "tool_call", "tool_name": name, "tool_input": args})
    if msg.text:
        items.append({"type": "agent", "content": msg.text})


def _apply_tool_result(msg: ToolMessage, items: list[dict], pending_quizzes: list[int]) -> None:
    if not pending_quizzes:
        return
    result = _parse_tool_result(msg.text or "")
    idx = pending_quizzes.pop(0)
    if isinstance(result, dict):
        if result.get("action") == "skipped":
            items[idx]["status"] = "skipped"
        elif "student_answer" in result:
            items[idx]["status"] = "answered"
            items[idx]["user_answer"] = result["student_answer"]
        items[idx]["quiz_id"] = result.get("question_id", "")


def _iter_tool_calls(message) -> list[tuple[str, dict]]:
    """安全遍历 tool_calls 为 (name, args)。从 streaming.py 迁入（Task 6 删 streaming）。"""
    tc = getattr(message, "tool_calls", None)
    if not tc or inspect.isawaitable(tc):
        return []
    try:
        return [
            (
                call.get("name", "") if isinstance(call, dict) else getattr(call, "name", ""),
                call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {}),
            )
            for call in tc
        ]
    except TypeError:
        return []


def _build_quiz_item(args: dict) -> dict:
    return {
        "type": "quiz",
        "quiz_id": "",
        "topic": args.get("topic", ""),
        "q_type": args.get("q_type", ""),
        "stem": args.get("stem", ""),
        "options": _coerce_options(args.get("options")),
        "status": "pending",
        "user_answer": None,
    }


def _coerce_options(raw_options) -> list:
    if isinstance(raw_options, str):
        try:
            raw_options = json.loads(raw_options)
        except (json.JSONDecodeError, TypeError):
            return [raw_options]
    return raw_options or []


def _parse_tool_result(content_str: str) -> dict:
    try:
        return json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_pending_quiz(state: dict) -> dict | None:
    """从 Server state（dict）取当前未答 quiz 的 interrupt 值。"""
    if not state.get("next"):
        return None
    for task in state.get("tasks") or []:
        for intr in task.get("interrupts") or []:
            if "value" in intr:
                return intr["value"]
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_history_extract.py -v`
Expected: 3 PASS。

- [ ] **Step 5: 改 `router.py` 的 `get_history` 去 agent 依赖**

`backend/src/tutoring/chat/router.py`，把：
```python
@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
) -> HistoryOut:
    await chat_sessions.get_readable_session(db_session, session_id, user)
    result = await chat_history.build_history(agent, session_id)
    return HistoryOut(**result)
```
改为：
```python
@router.get("/{session_id}/history", response_model=HistoryOut)
async def get_history(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> HistoryOut:
    await chat_sessions.get_readable_session(db_session, session_id, user)
    result = await chat_history.build_history(str(session_id))
    return HistoryOut(**result)
```
并从文件顶部移除不再使用的导入：`get_agent`、`CompiledStateGraph`（若 `router` 内已无其他用处）。

- [ ] **Step 6: 验证导入无误**

Run: `uv run python -c "import tutoring.main; print('ok')"`
Expected: 打印 `ok`（无循环导入、无缺失符号）。

- [ ] **Step 7: 提交**

```bash
git add backend/src/tutoring/chat/history.py backend/src/tutoring/chat/router.py backend/tests/test_history_extract.py
git commit -m "refactor(chat): history 数据源改 Server state + messages_from_dict，get_history 去 agent 依赖"
```

---

### Task 4: server_client.proxy_run_stream（httpx 透传 + 心跳多路复用）

**前置：** Task 1（确认 Server 路由形态）；`langgraph dev` 在跑。

**Files:**
- Modify: `backend/src/tutoring/chat/server_client.py`
- Test: `backend/tests/test_server_client.py`

**Interfaces:**
- Produces: `server_client.proxy_run_stream(thread_id: str, body: dict) -> AsyncIterator[bytes]`。Task 5 的 `proxy.py` 依赖它。透传 Server 原生 SSE 字节 + 每 15s 插入 `b": heartbeat\n\n"`。

- [ ] **Step 1: 在 `server_client.py` 末尾追加 `proxy_run_stream`**

```python
import asyncio
from typing import AsyncIterator

_HEARTBEAT_INTERVAL = 15.0


async def proxy_run_stream(thread_id: str, body: dict) -> AsyncIterator[bytes]:
    """透传 Server 的 /threads/{id}/runs/stream SSE 字节，叠加 15s 心跳。

    用 httpx 流式 POST；与一个心跳协程通过 asyncio.Queue 合并 yield。
    Server 路由形态以 Task 1 Step 8 确认结果为准（默认 /threads/{id}/runs/stream）。
    """
    url = f"{_base()}/threads/{thread_id}/runs/stream"
    out: asyncio.Queue = asyncio.Queue()

    async def pump_upstream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=body) as resp:
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        await out.put(("error", resp.status_code, text))
                        return
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            await out.put(("data", chunk))
        except Exception as e:  # noqa: BLE001
            await out.put(("exc", e))
        finally:
            await out.put(("done", None))

    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await out.put(("data", b": heartbeat\n\n"))
        except asyncio.CancelledError:
            return

    pump_task = asyncio.create_task(pump_upstream())
    hb_task = asyncio.create_task(heartbeat())
    try:
        while True:
            kind, *rest = await out.get()
            if kind == "data":
                yield rest[0]
            elif kind == "error":
                status, text = rest
                yield _sse_error(status, text)
                break
            elif kind == "exc":
                yield _sse_error(502, str(rest[0]).encode())
                break
            elif kind == "done":
                break
    finally:
        hb_task.cancel()
        pump_task.cancel()
        await asyncio.gather(hb_task, pump_task, return_exceptions=True)


def _sse_error(status: int, text: bytes) -> bytes:
    """把 Server 的非 2xx 透传为前端可识别的 SSE error 事件（保持网关错误体风格）。"""
    import json as _json
    msg = text.decode("utf-8", "replace")
    data = _json.dumps({"message": msg, "code": f"SERVER_{status}"}, ensure_ascii=False)
    return f"event: error\ndata: {data}\n\n".encode("utf-8")
```

- [ ] **Step 2: 写集成测试（需 Server 在跑）**

追加到 `backend/tests/test_server_client.py`：
```python
import pytest

from tutoring.chat.server_client import proxy_run_stream


@pytest.mark.skipif(
    True,  # 集成测试：需 langgraph dev 在跑；去掉 True 并确保 Server 运行后启用
    reason="需 langgraph dev 在 localhost:2024 运行",
)
async def test_proxy_run_stream_yields_bytes():
    body = {
        "assistant_id": "tutor",
        "input": {"messages": [{"role": "user", "content": "你好"}]},
        "stream_mode": ["messages", "updates"],
        "multitask_strategy": "reject",
        "on_disconnect": "continue",
        "if_not_exists": "create",
        "context": {"mode": "free", "course_name": "计算机网络"},
    }
    seen = []
    async for chunk in proxy_run_stream("__test_thread__", body):
        seen.append(chunk)
        if len(seen) > 3:
            break
    assert seen, "应至少收到一个 SSE 字节块"
    assert isinstance(seen[0], (bytes, bytearray))
```

- [ ] **Step 3: 手动集成验证**

确保 `langgraph dev` 在跑。临时把上面测试的 `skipif(True, ...)` 改为 `skipif(False, ...)`。
Run: `uv run pytest tests/test_server_client.py::test_proxy_run_stream_yields_bytes -v -s`
Expected: PASS（收到 SSE 字节）。验证后改回 `skipif(True, ...)`（默认跳过，避免 CI 需 Server）。

- [ ] **Step 4: 提交**

```bash
git add backend/src/tutoring/chat/server_client.py backend/tests/test_server_client.py
git commit -m "feat(chat): server_client.proxy_run_stream httpx 透传 SSE + 心跳多路复用"
```

---

### Task 5: proxy.py 伪装 Server 流式端点 + build_agent_context 返 dict

**前置：** Task 4 完成。

**Files:**
- Create: `backend/src/tutoring/chat/proxy.py`
- Modify: `backend/src/tutoring/chat/sessions.py`（`build_agent_context` 返 dict）
- Test: `backend/tests/test_proxy.py`

**Interfaces:**
- Consumes: `server_client.is_interrupted`、`server_client.proxy_run_stream`、`sessions.get_writable_session`、`sessions.build_agent_context`、`sessions.touch_session`
- Produces: `proxy.router`（`APIRouter`），路由 `POST /threads/{thread_id}/runs/stream`。Task 6 挂载它。

- [ ] **Step 1: 改 `sessions.build_agent_context` 返回 dict**

`backend/src/tutoring/chat/sessions.py`，把：
```python
async def build_agent_context(db: AsyncSession, sess: Session) -> AgentContext:
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)
```
改为：
```python
async def build_agent_context(db: AsyncSession, sess: Session) -> dict:
    """构造传给 Server 的 context dict（与 AgentContext 字段一致，Server 侧再强转）。"""
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return {
            "mode": "project",
            "course_name": settings.course_name,
            "project_name": proj.name if proj else "",
            "project_background_md": proj.background_md if proj else "",
        }
    return {"mode": "free", "course_name": settings.course_name}
```
并移除文件顶部不再使用的 `from tutoring.agent.prompts import AgentContext`（若文件内无其他引用）。

- [ ] **Step 2: 写 `proxy.py`**

```python
"""伪装 LangGraph Server 的流式端点：POST /threads/{thread_id}/runs/stream。

前端用 @langchain/langgraph-sdk 打这里。网关职责：鉴权 -> 加载 session ->
拼 context -> 注入并发/断线参数 -> is_interrupted 守卫 -> httpx 透传 Server SSE。
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.chat import server_client
from tutoring.chat import sessions as chat_sessions
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError

router = APIRouter(tags=["chat"])

_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


@router.post("/threads/{thread_id}/runs/stream")
async def runs_stream(
    thread_id: UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """透传 Server 的 runs/stream；前端 SDK 原生接收事件。"""
    sess = await chat_sessions.get_writable_session(db_session, thread_id, user)

    body = await request.json()
    tid = str(thread_id)

    # 保留前端传入的 input/command/stream_mode；注入服务端控制参数
    body["assistant_id"] = "tutor"
    body["context"] = await chat_sessions.build_agent_context(db_session, sess)
    body["multitask_strategy"] = "reject"
    body["on_disconnect"] = "continue"
    body.setdefault("if_not_exists", "create")

    is_input = "input" in body
    is_command = "command" in body
    interrupted = await server_client.is_interrupted(tid)

    if is_input and interrupted:
        raise AppError(409, "SESSION_INTERRUPTED", "Session is paused at a quiz; call /quiz/resume first")
    if is_command and not interrupted:
        raise AppError(409, "SESSION_NOT_INTERRUPTED", "Session is not paused; no quiz to resume")

    if is_input:
        await chat_sessions.touch_session(db_session, thread_id)

    return StreamingResponse(
        server_client.proxy_run_stream(tid, body),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
```

- [ ] **Step 3: 写集成测试（需 Server + DB）**

`backend/tests/test_proxy.py`：
```python
import pytest


@pytest.mark.skipif(True, reason="需 langgraph dev + 真实 DB；启用前确保服务在跑")
async def test_runs_stream_guard_interrupted(client, cleanup_db):
    """无 interrupt 时 resume 应 409 SESSION_NOT_INTERRUPTED。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]
    resp = await client.post(
        f"/threads/{sid}/runs/stream",
        json={"command": {"resume": {"action": "skip"}}, "stream_mode": ["messages", "updates"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_INTERRUPTED"
```

- [ ] **Step 4: 挂载并手动联调**

临时在 `main.py` 加 `from tutoring.chat import proxy as chat_proxy` + `app.include_router(chat_proxy.router)`（Task 6 正式整理）。启动 `uvicorn` + `langgraph dev`，把 `test_proxy.py` 的 skipif 改 `False`：
Run: `uv run pytest tests/test_proxy.py -v -s`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/src/tutoring/chat/proxy.py backend/src/tutoring/chat/sessions.py backend/tests/test_proxy.py
git commit -m "feat(chat): proxy.py 伪装 /threads/{id}/runs/stream + build_agent_context 返 dict"
```

---

### Task 6: main.py/deps.py 收尾 + 删除 streaming/tasks/sse + conftest

**前置：** Task 5 完成。

**Files:**
- Modify: `backend/src/tutoring/main.py`
- Modify: `backend/src/tutoring/core/deps.py`
- Modify: `backend/tests/conftest.py`
- Delete: `backend/src/tutoring/chat/streaming.py`、`backend/src/tutoring/chat/tasks.py`、`backend/src/tutoring/chat/sse.py`

**Interfaces:**
- 移除 `get_agent`；移除 lifespan 中 agent/checkpointer/rag；正式挂 `proxy.router`、移除 `sse_router`。

- [ ] **Step 1: 改 `main.py` lifespan + 挂载**

移除 lifespan 内：`AsyncPostgresSaver` 构造与 `async with`、`create_rag()` + `initialize_storages()` + `finalize_storages()`、`build_agent`、`app.state.agent/checkpointer/rag`。保留 DB engine/session_factory/init_db、CORS、LangSmith。lifespan 简化为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(settings.database_url)
    await init_db(engine)
    app.state.engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    logger.info("DB initialized: %s", settings.database_url)
    yield
    await engine.dispose()
    logger.info("Cleanup complete")
```

导入与挂载：移除 `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`、`from tutoring.core.lightrag import create_rag`、`from tutoring.chat import sse as chat_sse_router`、`from tutoring.agent.factory import build_agent`。改为：
```python
from tutoring.chat import router as chat_rest_router
from tutoring.chat import proxy as chat_proxy_router
```
挂载：
```python
app.include_router(chat_rest_router.router)
app.include_router(chat_proxy_router.router)
```
（移除原 `chat_sse_router` 挂载。）

- [ ] **Step 2: 改 `core/deps.py` 删 `get_agent`**

删除：
```python
def get_agent(request: Request) -> CompiledStateGraph:
    return request.app.state.agent
```
及其相关导入（`CompiledStateGraph` 若无其他引用）。

- [ ] **Step 3: 删除三个文件**

Run:
```bash
git rm backend/src/tutoring/chat/streaming.py backend/src/tutoring/chat/tasks.py backend/src/tutoring/chat/sse.py
```

- [ ] **Step 4: 验证导入与编译**

Run: `uv run python -c "import tutoring.main; print('ok')"` && `uv run python -m compileall -q src/tutoring`
Expected: 打印 `ok`；compileall 退出 0。

- [ ] **Step 5: 更新 `conftest.py` 说明 Server 前置**

在 `backend/tests/conftest.py` 顶部 docstring 追加：
```python
"""测试 fixture：真实 ASGI client + 测试数据清理。

集成测试（test_chat_streaming / test_proxy / test_server_client 等）额外需要
`langgraph dev` 在 http://localhost:2024 运行（langgraph_server_url 默认指向它）。
"""
```
（fixture 本身不变——FastAPI 经网关调 Server。）

- [ ] **Step 6: 全量验证**

确保 `langgraph dev` 在跑。Run: `uv run python -c "import tutoring.main; print('ok')"`
Expected: `ok`。
Run（启用 Task 4/5 的集成测试 skipif=False 后）: `uv run pytest tests/test_server_client.py tests/test_proxy.py tests/test_history_extract.py -v`
Expected: 全 PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/src/tutoring/main.py backend/src/tutoring/core/deps.py backend/tests/conftest.py
git commit -m "refactor(chat): main/deps 去 agent/checkpointer/rag，挂 proxy.router，删 streaming/tasks/sse"
```

---

## 前端适配（后续独立计划）

前端接入 `@langchain/langgraph-sdk`：`api/chat.ts` 改用 `client.runs.stream(sessionId, "tutor", {input|command, stream_mode:["messages","updates"]})` 指向 FastAPI base URL；`stores/chat.ts` 改为处理原生事件（`messages/partial` 累积 token、`updates` 里 `__interrupt__` 取 quiz 载荷、`end`/`error`）。前端无测试框架，仅 `npm run typecheck` + 手动联调。**单独立计划**（不同语言/测试栈）。

## Self-Review

**1. Spec 覆盖：**
- §3 拓扑（网关伪装 Server）→ Task 5 + Task 6 挂载 ✓
- §4.1 agent/server_runtime + build_agent 解耦 → Task 1 ✓
- §4.2 chat 模块表（proxy/server_client/history/sessions/删除 streaming+tasks+sse_router）→ Task 2/3/4/5/6 ✓
- §4.2 deps 删 get_agent、main lifespan → Task 6 ✓
- §5 透传原生 SSE + 心跳 → Task 4 ✓
- §6.1/6.2 send/resume 流程 + 守卫 → Task 5 ✓
- §6.3 history（get_state + messages_from_dict + _extract_items + processing）→ Task 3 ✓
- §6.4 并发（multitask_strategy=reject）→ Task 5 注入 ✓
- §6.5 断线（on_disconnect=continue）→ Task 5 注入 ✓
- §7 langgraph.json + 依赖 + config + 开发命令 → Task 1/2 ✓
- §8 thread_id=session_id → Task 5（tid=str(thread_id)）✓
- §11 开放问题：11.1/11.4/11.5 由 Task 1 验证步骤覆盖；11.2 由 Task 5 _build_introspect_agent 规避；11.3 has_active_run 可降级（Task 2 实现，Task 3 使用）；11.6 心跳 Task 4；11.7 LightRAG 生命周期 Task 1 factory（实现时评估）✓
- §12 验收：Task 6 Step 6 集成验证覆盖流式/interrupt/history/并发；断线持久需手动验证（在 Task 6 Step 6 备注）

**2. Placeholder 扫描：** 无 TBD/TODO；Task 1 Step 8/Step 7 是验证步骤（有具体命令与期望），非占位。集成测试用 `skipif(True)` 默认跳过是有意设计（需外部服务），非占位。

**3. 类型一致性：**
- `build_agent(*, rag, checkpointer=None)` — Task 1 定义，Task 1 server_runtime 调用一致 ✓
- `get_state(thread_id: str) -> dict`、`state_is_interrupted(state: dict) -> bool`、`is_interrupted(thread_id: str) -> bool`、`has_active_run(thread_id: str) -> bool`、`proxy_run_stream(thread_id: str, body: dict) -> AsyncIterator[bytes]` — Task 2/4 定义，Task 3/5 消费一致 ✓
- `build_history(thread_id: str) -> dict` — Task 3 定义，router.py 调用 `build_history(str(session_id))` 一致 ✓
- `build_agent_context(db, sess) -> dict` — Task 5 改造，proxy.py 调用一致 ✓
- `_extract_pending_quiz(state: dict)` — Task 3 改 dict，测试一致 ✓

**遗留注意：** Task 1 Step 7/8 的验证结论可能要求微调 Task 4 的透传 URL 或 Task 5 的路由路径（若 SDK 实际路由非 `/threads/{id}/runs/stream`）。已在 Task 4 Step 1 注明以 Task 1 结论为准。

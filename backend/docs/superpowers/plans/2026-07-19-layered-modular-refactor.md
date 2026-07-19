# 分层模块化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 FastAPI 后端从按技术分层（api/db/schemas）重组为特性模块 + 共享数据层，消除重复代码、统一错误处理，为教师端/学生端与认证体系铺路。

**Architecture:** 方案 A（特性模块 + 共享数据层）：`projects/ chat/ knowledge/ agent/` 四个领域模块 + `core/` 共享内核 + `db/` 集中数据层，依赖方向单向（`core ← db ← agent ← chat`，`knowledge ← agent`）。纯内部重构，API 契约零变更。

**Tech Stack:** Python 3.13 / uv / FastAPI / SQLModel / LangGraph 1.x / LangChain 1.x / pytest（集成测试，真实 DB + LightRAG + LLM）

**Spec:** `docs/superpowers/specs/2026-07-19-layered-modular-refactor-design.md`

## Global Constraints

- **API 契约不变**：所有 URL 路径、请求/响应 schema、SSE 事件类型（`text/quiz_interrupt/done/error`）不变
- **错误体格式字节级不变**：`{"detail": {"error": {"code": "...", "message": "..."}}}` —— 必须保留 `detail` 外层（现有测试断言此结构）
- 现有 6 个测试文件只许改 import 路径，不许改断言
- 不新增/删除 `pyproject.toml` 依赖；无 ruff/pre-commit 门槛
- LangGraph checkpoint 机制、prompt 内容、`quiz_flow` 幂等逻辑不动
- 验收：`uv run pytest` 全绿
- 所有工作目录：`/Volumes/ExternalStorageA/project/2026.7/教学Agent/teaching_agent_api`

---

### Task 1: core/ + db/ 基础设施落地

**Files:**
- Create: `src/teaching_agent_api/core/__init__.py`（空）
- Create: `src/teaching_agent_api/core/config.py`（从 `config.py` 平移，内容不变）
- Create: `src/teaching_agent_api/core/database.py`（从 `db/engine.py` 平移，import 改为 `from teaching_agent_api.db import models`）
- Create: `src/teaching_agent_api/core/errors.py`（新，见下方代码）
- Create: `src/teaching_agent_api/core/deps.py`（从 `deps.py` 平移 + 新增 `CurrentUser`/`get_current_user`，见下方代码）
- Create: `src/teaching_agent_api/core/health.py`（从 `api/health.py` 平移，内容不变）
- Modify: `src/teaching_agent_api/db/repos.py`（所有函数参数 `db: AsyncSession` → `session: AsyncSession`，函数体同步改名；逻辑零变化）
- Modify: `src/teaching_agent_api/db/__init__.py`（移除 engine 三个函数的 re-export，其余不变）
- Modify: `src/teaching_agent_api/main.py`（import 更新 + 注册异常 handler，见下方代码）
- Modify: `src/teaching_agent_api/api/*.py`、`src/teaching_agent_api/agent/*.py`（仅 import 路径：`config` → `core.config`，`db.engine` → `core.database`，`deps` → `core.deps`）
- Modify: `tests/conftest.py`（`config` → `core.config`，`db.engine` → `core.database`）
- Delete: `src/teaching_agent_api/config.py`、`src/teaching_agent_api/deps.py`、`src/teaching_agent_api/db/engine.py`、`src/teaching_agent_api/api/health.py`
- Test: `tests/test_errors.py`（新，见下方代码）

**Interfaces:**
- Produces:
  - `core.errors.AppError(status: int, code: str, message: str)`、`core.errors.LightRAGError`、`core.errors.register_exception_handlers(app: FastAPI) -> None`
  - `core.deps.CurrentUser(id: str, role: str = "student")`、`core.deps.get_current_user(...) -> CurrentUser`
  - `core.deps.get_db / get_user_id(保留) / get_lightrag_client / get_agent`
  - `core.database.create_engine / create_session_factory / init_db`
  - `core.config.settings`
- Consumes: 无（首个任务）

- [ ] **Step 1: 写失败测试 `tests/test_errors.py`**

```python
"""统一错误格式测试。"""
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from teaching_agent_api.core.errors import (
    AppError,
    LightRAGError,
    register_exception_handlers,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def app_error():
        raise AppError(404, "SESSION_NOT_FOUND", "Session abc not found")

    @app.get("/lightrag-error")
    async def lightrag_error():
        raise LightRAGError("connection refused")

    return app


async def test_app_error_format():
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        resp = await c.get("/app-error")
    assert resp.status_code == 404
    assert resp.json() == {
        "detail": {"error": {"code": "SESSION_NOT_FOUND", "message": "Session abc not found"}}
    }


async def test_lightrag_error_format():
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        resp = await c.get("/lightrag-error")
    assert resp.status_code == 502
    assert resp.json() == {
        "detail": {"error": {"code": "LIGHTRAG_ERROR", "message": "connection refused"}}
    }


async def test_api_404_format_unchanged(client):
    """契约回归：真实 API 的 404 保持 detail 包裹格式。"""
    resp = await client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL（`ModuleNotFoundError: teaching_agent_api.core`）

- [ ] **Step 3: 创建 core/ 全部新文件**

`core/errors.py`：

```python
"""统一错误类型与异常处理器。对外格式：{"detail": {"error": {"code", "message"}}}。"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务错误，handler 转为带 detail 包裹的统一错误体。"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class LightRAGError(Exception):
    """LightRAG 上游调用失败，handler 转 502。"""


def _error_body(code: str, message: str) -> dict:
    return {"detail": {"error": {"code": code, "message": message}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=_error_body(exc.code, exc.message))

    @app.exception_handler(LightRAGError)
    async def lightrag_error_handler(request: Request, exc: LightRAGError) -> JSONResponse:
        return JSONResponse(status_code=502, content=_error_body("LIGHTRAG_ERROR", str(exc)))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_error_body("INTERNAL_ERROR", str(exc)))
```

`core/deps.py`（在原 deps.py 基础上新增，保留 `get_user_id` 兼容）：

```python
"""FastAPI 依赖注入。"""
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import Request, Header
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.knowledge.client import LightRAGClient  # Task 2 前为 lightrag.client


@dataclass(frozen=True)
class CurrentUser:
    """当前请求用户。未来由 auth/ 模块的 JWT 校验填充 role。"""

    id: str
    role: str = "student"


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """每请求的 DB session。"""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        yield session


def get_current_user(x_user_id: str | None = Header(None, alias="X-User-Id")) -> CurrentUser:
    """无 header 时默认为 demo-student。未来改为委托 auth/ 模块校验 JWT。"""
    return CurrentUser(id=x_user_id or "demo-student")


def get_user_id(x_user_id: str | None = Header(None, alias="X-User-Id")) -> str:
    """兼容旧签名，Task 4 后删除。"""
    return x_user_id or "demo-student"


def get_lightrag_client(request: Request) -> LightRAGClient:
    return request.app.state.lightrag_client


def get_agent(request: Request) -> CompiledStateGraph:
    return request.app.state.agent
```

注意：上面 `LightRAGClient` 的 import 在 Task 1 时仍写 `from teaching_agent_api.lightrag.client import LightRAGClient`，Task 2 再改。

- [ ] **Step 4: 平移文件 + 更新全部 import**

`git mv` 等效操作（新建目标文件、删除旧文件）。`main.py` 在 lifespan 之后、路由挂载之前插入：

```python
from teaching_agent_api.core.errors import register_exception_handlers

app = FastAPI(title="Teaching Agent API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
```

main.py 其余 import：`config` → `core.config`、`db.engine` → `core.database`、`api.health` → `core.health`。

- [ ] **Step 5: 全量测试 + 提交**

Run: `uv run pytest -v`
Expected: 全绿（含新 test_errors.py 3 个测试）

```bash
git add -A && git commit -m "refactor: Task 1 -- core/ + db/ 基础设施（统一错误处理 + CurrentUser 占位）"
```

---

### Task 2: knowledge/ 代理合并与瘦身

**Files:**
- Create: `src/teaching_agent_api/knowledge/__init__.py`（空）
- Create: `src/teaching_agent_api/knowledge/client.py`（从 `lightrag/client.py` 移入 + `LightRAGError` 包装，见下方代码）
- Create: `src/teaching_agent_api/knowledge/router.py`（合并 documents + graph 共 13 个端点，全部单行）
- Modify: `src/teaching_agent_api/main.py`（路由 import：`api.documents`/`api.graph` → `knowledge.router`；lifespan 中 `lightrag.client` → `knowledge.client`）
- Modify: `src/teaching_agent_api/agent/tools.py`（import `lightrag.client` → `knowledge.client`）
- Modify: `src/teaching_agent_api/core/deps.py`（import 同步）
- Delete: `src/teaching_agent_api/lightrag/`（整个目录含 schemas.py——LightRAG 响应体一直按 dict 透传，schemas.py 无引用，确认后删除）、`src/teaching_agent_api/api/documents.py`、`src/teaching_agent_api/api/graph.py`

**Interfaces:**
- Consumes: `core.errors.LightRAGError`（Task 1）
- Produces: `knowledge.client.LightRAGClient`（方法签名不变，失败时抛 `LightRAGError` 而非 `httpx.HTTPError`）；`knowledge.router.router`

- [ ] **Step 1: client.py 移入并加 LightRAGError 包装**

文件头部加：

```python
from teaching_agent_api.core.errors import LightRAGError
```

新增私有 helper，并把所有方法体改为走它（机械替换 `resp = await self.client.get/post/request(...)` + `resp.raise_for_status()`）：

```python
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """统一请求入口：httpx 错误包装为 LightRAGError（由全局 handler 转 502）。"""
        try:
            resp = await self.client.request(method, url, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise LightRAGError(str(e)) from e
        return resp
```

示例改写（其余 15 个方法同模式）：

```python
    async def scan(self) -> dict:
        """POST /documents/scan（触发增量扫描）。"""
        resp = await self._request("POST", "/documents/scan")
        return resp.json()

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        """POST /documents/upload（multipart）。"""
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self._request("POST", "/documents/upload", files=files)
        return resp.json()

    async def search_labels(self, query: str) -> list[str]:
        """GET /graph/label/search。注意：LightRAG API 用 `q` 作为查询参数名。"""
        resp = await self._request("GET", "/graph/label/search", params={"q": query})
        return resp.json()
```

- [ ] **Step 2: knowledge/router.py —— 13 个单行端点**

```python
"""LightRAG 代理端点（documents + graph 合并）。纯透传，错误由全局 handler 转 502。"""
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File

from teaching_agent_api.core.deps import get_lightrag_client
from teaching_agent_api.knowledge.client import LightRAGClient

router = APIRouter(tags=["knowledge"])


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    content = await file.read()
    return await lightrag.upload_file(
        content, file.filename or "unknown", file.content_type or "application/octet-stream"
    )


@router.post("/documents/text")
async def insert_text(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.insert_text(await request.json())


@router.post("/documents/texts")
async def insert_texts(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.insert_texts(await request.json())


@router.post("/documents/scan")
async def scan(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.scan()


@router.get("/documents/track_status/{track_id}")
async def track_status(track_id: str, lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.track_status(track_id)


@router.get("/documents/pipeline_status")
async def pipeline_status(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.pipeline_status()


@router.get("/documents/status_counts")
async def status_counts(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.status_counts()


@router.post("/documents/paginated")
async def list_documents(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.list_documents(await request.json())


@router.delete("/documents/delete_document")
async def delete_documents(request: Request, lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.delete_documents(await request.json())


@router.get("/graph/label/list")
async def list_labels(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> list[str]:
    return await lightrag.list_labels()


@router.get("/graph/label/popular")
async def popular_labels(
    limit: int = Query(300, ge=1, le=1000),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    return await lightrag.popular_labels(limit=limit)


@router.get("/graph/label/search")
async def search_labels(
    query: str = Query(..., min_length=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    return await lightrag.search_labels(query=query)


@router.get("/graphs")
async def get_graph(
    label: str = Query(..., min_length=1),
    max_depth: int = Query(3, ge=1),
    max_nodes: int = Query(1000, ge=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.get_graph(label=label, max_depth=max_depth, max_nodes=max_nodes)
```

注意：合并后 OpenAPI tags 从 `documents`/`graph` 变为 `knowledge`（仅影响文档分组，URL 不变）。

- [ ] **Step 3: main.py + 全量 import 更新，删旧文件，测试，提交**

Run: `uv run pytest -v`（重点：`tests/test_documents_proxy.py` 6 个测试原样通过）
Expected: 全绿

```bash
git add -A && git commit -m "refactor: Task 2 -- knowledge/ 代理合并，13 端点瘦身 + LightRAGError 统一 502"
```

---

### Task 3: agent/ 工具工厂化（去全局状态）

**Files:**
- Modify: `src/teaching_agent_api/agent/tools.py`（删 `_state`/`set_dependencies()`/`_get_lightrag()`/`_db_session()`，改为 `make_tools()` 闭包工厂，见下方代码；其余逻辑逐字保留）
- Modify: `src/teaching_agent_api/agent/factory.py`（`build_agent` 接收 tools 参数）
- Modify: `src/teaching_agent_api/main.py`（lifespan 改调 `make_tools` + 新签名 `build_agent`）
- Test: `tests/test_agent_tools.py`（新）

**Interfaces:**
- Consumes: `knowledge.client.LightRAGClient`（Task 2）
- Produces:
  - `agent.tools.make_tools(*, lightrag_client: LightRAGClient, db_session_factory: async_sessionmaker[AsyncSession]) -> list[BaseTool]`，返回 `[search_knowledge, quiz_flow]`（工具名、docstring、quiz_flow 内部逻辑不变）
  - `agent.factory.build_agent(checkpointer: BaseCheckpointSaver, tools: list[BaseTool]) -> CompiledStateGraph`

- [ ] **Step 1: 写失败测试 `tests/test_agent_tools.py`**

```python
"""make_tools 工厂测试：替代原模块级 _state 隐式注入。"""
from teaching_agent_api.agent.tools import make_tools
from teaching_agent_api.core.config import settings
from teaching_agent_api.core.database import create_engine, create_session_factory
from teaching_agent_api.knowledge.client import LightRAGClient


async def test_make_tools_returns_expected_tools():
    lightrag = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    engine = create_engine(settings.database_url)
    tools = make_tools(
        lightrag_client=lightrag,
        db_session_factory=create_session_factory(engine),
    )
    assert [t.name for t in tools] == ["search_knowledge", "quiz_flow"]
    await engine.dispose()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: FAIL（`ImportError: cannot import name 'make_tools'`）

- [ ] **Step 3: tools.py 改为工厂**

结构如下（`search_knowledge` / `quiz_flow` 函数体与现有实现逐字相同，只是移入闭包并把 `_get_lightrag()` 换成 `lightrag_client`、`_db_session()` 换成局部 asynccontextmanager）：

```python
"""Agent 工具工厂：make_tools() 闭包注入依赖，替代模块级全局态。"""
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from teaching_agent_api.agent.llm import get_llm
from teaching_agent_api.agent.prompts import QUIZ_GENERATION_PROMPT, EVALUATION_PROMPT
from teaching_agent_api.core.config import settings
from teaching_agent_api.db import repos
from teaching_agent_api.knowledge.client import LightRAGClient

# QuizOutput / EvaluationOutput 两个结构化输出 schema 原样保留在本模块
# （含 _coerce_options validator），此处不重复展示。

logger = logging.getLogger(__name__)


def make_tools(
    *,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> list[BaseTool]:
    """构建 agent 工具列表，闭包捕获依赖。"""

    @asynccontextmanager
    async def _db_session():
        async with db_session_factory() as session:
            yield session

    async def _search_for_quiz(topic: str) -> str:
        try:
            result = await lightrag_client.query(query=topic, mode="mix", only_need_context=True)
            return result.get("response", "") or ""
        except Exception as e:
            logger.warning("出题素材检索失败: %s", e)
            return ""

    async def _generate_quiz(topic: str, context: str) -> QuizOutput:
        llm = get_llm().with_structured_output(QuizOutput, method="function_calling")
        return await llm.ainvoke(
            QUIZ_GENERATION_PROMPT.format(
                course_name=settings.course_name,
                topic=topic,
                context=context or "（无检索结果）",
            )
        )

    async def _evaluate_answer(stem, q_type, correct_answer, user_answer) -> EvaluationOutput:
        llm = get_llm().with_structured_output(EvaluationOutput, method="function_calling")
        return await llm.ainvoke(
            EVALUATION_PROMPT.format(
                stem=stem, q_type=q_type,
                correct_answer=correct_answer, student_answer=user_answer,
            )
        )

    @tool
    async def search_knowledge(query: str) -> str:
        """检索课程知识库（知识图谱 + RAG），返回相关知识片段。

        当学生提问或讨论某个概念时，先调用此工具检索相关知识，
        再基于检索内容设计苏格拉底式追问。检索结果包含向量匹配和知识图谱扩展的片段。

        Args:
            query: 检索关键词，需包含完整上下文（消除代词指代）
        """
        # 函数体与原实现逐字相同，_get_lightrag() → lightrag_client

    @tool
    async def quiz_flow(topic: str, config: RunnableConfig) -> str:
        """出一道关于指定知识点的题目，等待学生作答后返回评估结果。

        当学生说"考考我"、需要检验理解程度、或你判断时机成熟时调用此工具。
        调用后会暂停等待学生答题，学生提交答案后自动判分。

        Args:
            topic: 要出题的知识点名称
        """
        # 函数体与原实现逐字相同（含 interrupt 幂等逻辑），
        # _db_session() 用闭包内版本，db.xxx → repos.xxx

    return [search_knowledge, quiz_flow]
```

`factory.py`：

```python
def build_agent(checkpointer: BaseCheckpointSaver, tools: list[BaseTool]) -> CompiledStateGraph:
    """构建 agent。生产由 lifespan 调用一次；测试每个 lifespan 重建。"""
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
```

`main.py` lifespan 第 4、5 步改为：

```python
        # 4. 构建工具（闭包注入 LightRAGClient + DB session factory）
        from teaching_agent_api.agent.tools import make_tools
        tools = make_tools(
            lightrag_client=lightrag_client,
            db_session_factory=db_session_factory,
        )

        # 5. 构建 agent 单例
        app.state.agent = None
        try:
            from teaching_agent_api.agent.factory import build_agent
            app.state.agent = build_agent(checkpointer, tools)
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent 构建失败: %s", e)
```

- [ ] **Step 4: 全量测试 + 提交**

Run: `uv run pytest -v`（重点：`tests/test_chat_streaming.py` —— quiz interrupt/resume 行为不变）
Expected: 全绿

```bash
git add -A && git commit -m "refactor: Task 3 -- agent 工具工厂化，消除模块级全局态"
```

---

### Task 4: projects/ + chat/ 领域模块落地

**Files:**
- Create: `src/teaching_agent_api/projects/__init__.py`（空）
- Create: `src/teaching_agent_api/projects/schemas.py`（从 `schemas/project.py` 平移，内容不变）
- Create: `src/teaching_agent_api/projects/service.py`（新，见下方代码）
- Create: `src/teaching_agent_api/projects/router.py`（从 `api/projects.py` 改薄：业务判断进 service，路由只调 service + model_validate）
- Create: `src/teaching_agent_api/chat/__init__.py`（空）
- Create: `src/teaching_agent_api/chat/schemas.py`（合并 `schemas/session.py` + `schemas/chat.py`，内容不变）
- Create: `src/teaching_agent_api/chat/service.py`（合并两份会话校验 + 搬迁编排逻辑，见下方代码）
- Create: `src/teaching_agent_api/chat/router.py`（原 `api/sessions.py` 改薄）
- Create: `src/teaching_agent_api/chat/sse.py`（原 `api/chat.py` 改薄）
- Modify: `src/teaching_agent_api/main.py`（路由 import 更新）
- Delete: `src/teaching_agent_api/api/`（整个目录）、`src/teaching_agent_api/schemas/`（整个目录）、`core/deps.py` 中的 `get_user_id`

**Interfaces:**
- Consumes: `core.errors.AppError`、`core.deps.CurrentUser/get_current_user`（Task 1）、`db.repos`（Task 1 改名后签名）、`projects/service.py` 被 chat 消费
- Produces:
  - `projects.service.create_project(db, *, name, background_md, status) -> Project`（重名时 `AppError(409, "PROJECT_NAME_CONFLICT", ...)`）
  - `projects.service.get_project_or_404(db, project_id) -> Project`
  - `projects.service.get_published_project(db, project_id) -> Project`（404 `PROJECT_NOT_FOUND` / 422 `PROJECT_NOT_PUBLISHED`）
  - `chat.service.get_owned_session(db, session_id, user_id) -> Session`（404 `SESSION_NOT_FOUND` / 403 `FORBIDDEN`）
  - `chat.service.get_active_session(db, session_id, user_id) -> Session`（同上 + 409 `SESSION_ENDED`）
  - `chat.service.build_agent_context(db, sess) -> AgentContext`
  - `chat.service.is_interrupted(agent, session_id) -> bool`
  - `chat.service.session_to_out_dict(sess, project=None) -> dict`（原 `_enrich_session` 逻辑逐字搬迁）

- [ ] **Step 1: projects/service.py**

```python
"""Project 领域服务：业务规则集中于此。"""
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.core.errors import AppError
from teaching_agent_api.db import repos
from teaching_agent_api.db.models import Project


async def create_project(
    db: AsyncSession, *, name: str, background_md: str, status: str = "draft"
) -> Project:
    try:
        return await repos.create_project(
            db, name=name, background_md=background_md, status=status
        )
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "PROJECT_NAME_CONFLICT", f"Project name '{name}' already exists")


async def get_project_or_404(db: AsyncSession, project_id: UUID) -> Project:
    proj = await repos.get_project(db, project_id)
    if not proj:
        raise AppError(404, "PROJECT_NOT_FOUND", f"Project {project_id} not found")
    return proj


async def get_published_project(db: AsyncSession, project_id: UUID) -> Project:
    """确保 project 存在且已发布（开会话的前置规则）。"""
    proj = await get_project_or_404(db, project_id)
    if proj.status != "published":
        raise AppError(422, "PROJECT_NOT_PUBLISHED", "Project must be published to start a session")
    return proj
```

`projects/router.py` 示例（改薄后模式，其余端点同构）：

```python
@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    body: ProjectCreate, db_session: AsyncSession = Depends(get_db)
) -> ProjectOut:
    proj = await project_service.create_project(
        db_session, name=body.name, background_md=body.background_md, status=body.status
    )
    return ProjectOut.model_validate(proj)
```

注意路由函数名不能与 service 函数同名（`create_project` → `create_project_endpoint`），避免模块内遮蔽。

- [ ] **Step 2: chat/service.py**

```python
"""会话领域服务：404/403/409 校验全项目唯一一份。"""
import uuid

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.core.config import settings
from teaching_agent_api.core.errors import AppError
from teaching_agent_api.db import repos
from teaching_agent_api.db.models import Project, Session


async def get_owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """存在且归属该用户，否则抛 404/403。"""
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if sess.user_id != user_id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def get_active_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """get_owned_session + 状态 active（chat 流式端点用）。"""
    sess = await get_owned_session(db, session_id, user_id)
    if sess.status != "active":
        raise AppError(409, "SESSION_ENDED", "Session is ended")
    return sess


async def build_agent_context(db: AsyncSession, sess: Session) -> AgentContext:
    """根据 session 模式构建 AgentContext；project 模式查项目信息。"""
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


async def is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    """检查 LangGraph state 是否处于 interrupt 待恢复状态。"""
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await agent.aget_state(config)
    return bool(state.next)


def session_to_out_dict(sess: Session, project: Project | None = None) -> dict:
    """原 api/sessions.py::_enrich_session 逻辑逐字搬迁（含 selectinload 防御注释）。"""
```

- [ ] **Step 3: chat/router.py + chat/sse.py 改薄**

- 路由全部改用 `user: CurrentUser = Depends(get_current_user)`，使用处 `user_id` → `user.id`
- REST 端点调 `chat.service.get_owned_session`；SSE 端点调 `get_active_session` + `is_interrupted`
- `create_session` 中 `mode == "project"` 时调 `projects.service.get_published_project`（chat → projects 单向依赖，符合 DAG）
- `session_to_out_dict` 替代 `_enrich_session`；SSE 流 try/finally 中 `repos.touch_session` 不变
- sse.py 端点路径保持 `/chat/sessions/{session_id}/messages` 与 `/chat/sessions/{session_id}/quiz/resume`（router prefix `/chat`）

- [ ] **Step 4: 全量测试 + 提交**

Run: `uv run pytest -v`（重点：`test_projects.py`/`test_sessions.py` 断言一字未改仍通过）
Expected: 全绿

```bash
git add -A && git commit -m "refactor: Task 4 -- projects/ + chat/ 领域模块，service 层落地 + 路由改薄"
```

---

### Task 5: main.py 终态 + auth/ 占位 + 文档收尾

**Files:**
- Create: `src/teaching_agent_api/auth/__init__.py`（占位模块，docstring 说明未来职责）
- Modify: `src/teaching_agent_api/main.py`（确认最终组装形态，见下方代码）
- Modify: `README.md`（Layout 一节重写为新结构）
- Modify: `AGENTS.md`（当前为空，写入项目结构、依赖规则、测试与运行命令）

**Interfaces:**
- Consumes: 前 4 个任务的全部产物
- Produces: 最终组装；`auth/` 占位（未来 JWT 校验器落点）

- [ ] **Step 1: auth/ 占位**

```python
"""认证授权模块（预留）。

当前认证由 core.deps.get_current_user 以 X-User-Id 请求头实现。
未来在此落地：JWT 校验器、User 模型、role（teacher/student）判定；
core.deps.get_current_user 将改为委托本模块，路由签名不变。
"""
```

- [ ] **Step 2: main.py 终态确认**

最终 import 块应为：

```python
from teaching_agent_api.core.config import settings
from teaching_agent_api.core.database import create_engine, create_session_factory, init_db
from teaching_agent_api.core.errors import register_exception_handlers
from teaching_agent_api.core import health as health_router
from teaching_agent_api.projects import router as projects_router
from teaching_agent_api.chat import router as chat_rest_router
from teaching_agent_api.chat import sse as chat_sse_router
from teaching_agent_api.knowledge import router as knowledge_router
```

lifespan 中延迟 import 保持 Task 3 形态（`make_tools`/`build_agent`）。`include_router` 6 个：health、projects、chat REST、chat SSE、knowledge。确认无 `api.`/`schemas.`/`lightrag.`/`db.engine` 残留 import：

Run: `rg -n "teaching_agent_api\.(api|schemas|lightrag)|db\.engine|from teaching_agent_api import (config|deps)" src/ tests/`
Expected: 零输出

- [ ] **Step 3: README Layout + AGENTS.md 重写**

README 的 Layout 代码块替换为新目录树（与 spec §3 一致）。AGENTS.md 写入：

```markdown
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

- 运行：`uv run uvicorn teaching_agent_api.main:app --reload --host 0.0.0.0 --port 8000`
- 测试：`uv run pytest`（集成测试，需真实 DB + LightRAG + DashScope，见 .env）
- 无 lint 工具（项目已移除 ruff）

## 约定

- 错误：raise `core.errors.AppError(status, code, message)`，对外格式 `{"detail": {"error": {...}}}` 不可变
- 路由依赖 `get_current_user`（CurrentUser.id/.role），不直接读 header
- agent 工具通过 `make_tools()` 闭包注入依赖，禁止模块级全局态
```

- [ ] **Step 4: 全量测试 + 提交**

Run: `uv run pytest -v`
Expected: 全绿（6 个原测试文件 + test_errors.py + test_agent_tools.py）

```bash
git add -A && git commit -m "refactor: Task 5 -- auth/ 占位 + README/AGENTS.md 同步新结构"
```

---

## Self-Review 记录

- **Spec 覆盖**：§3 目录（Task 1-5 全覆盖，health.py 落点定为 `core/health.py`，spec 未明示，已在此锁定）；§4 依赖规则（Task 4 chat→projects 单向，不违反 DAG）；§5.1-5.5（Task 1/2/3/4 分别对应）；§6 七步合并为 5 task（步骤 1+2→Task 1，3→Task 2，4→Task 3，5→Task 4，6+7→Task 5）；§7 测试策略（Task 1 test_errors.py、Task 3 test_agent_tools.py、契约回归逐 task 验证）
- **类型一致性**：`make_tools(*, lightrag_client, db_session_factory)` 与 `build_agent(checkpointer, tools)` 签名在 Task 3 定义、Task 5 main.py 使用一致；`AppError(status, code, message)` 全部任务一致；`LightRAGError` Task 1 定义、Task 2 使用一致
- **占位符扫描**：tools.py 两个工具函数体标注"逐字保留原实现"（文件迁移场景，非占位）；其余新代码均完整给出

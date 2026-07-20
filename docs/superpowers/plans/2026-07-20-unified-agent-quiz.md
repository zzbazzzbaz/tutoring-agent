# Unified Agent Quiz Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `quiz_flow` sub-agent tool (which internally makes 2 isolated LLM calls) with a thin `present_question` tool, so the main agent does all quiz generation and evaluation in its own reasoning context.

**Architecture:** The main agent generates quiz content as tool arguments, the `present_question` tool only handles DB persistence + `interrupt()` for HITL + returning the student's answer. The main agent then evaluates in its own response text. The agent module's only public API becomes `build_agent()`, with SSE/DB orchestration migrated to `chat/sse.py`.

**Tech Stack:** Python 3.13, FastAPI, LangChain 1.x (`create_agent`), LangGraph (`interrupt`, `Command(resume=...)`), SQLModel, asyncpg, pytest (integration tests with real DB + LightRAG + DashScope).

## Global Constraints

- Python >=3.13, use `uv run pytest` for tests (asyncio_mode = "auto")
- Tests are integration tests: real DB + LightRAG + DashScope LLM, no mocks
- LangChain 1.x patterns: `@tool` decorator, `interrupt()` from `langgraph.types`, `RunnableConfig` for thread_id
- Error handling: `raise core.errors.AppError(status, code, message)`
- No comments in code unless explicitly requested
- DB schema unchanged (verdict/diagnosis columns stay, just not populated)
- SSE event structure unchanged (quiz_interrupt / text / done / error)
- Frontend unchanged (QuizCard already handles null verdict/diagnosis)

---

### Task 1: Rewrite agent module (schemas + prompts + tools + factory)

**Files:**
- Modify: `backend/src/tutoring/agent/schemas.py`
- Modify: `backend/src/tutoring/agent/prompts.py`
- Modify: `backend/src/tutoring/agent/tools.py`
- Modify: `backend/src/tutoring/agent/factory.py`
- Modify: `backend/tests/test_agent_schemas.py`
- Modify: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `LightRAGClient`, `async_sessionmaker[AsyncSession]`, `BaseCheckpointSaver` (from main.py lifespan)
- Produces: `build_agent(checkpointer, lightrag_client, db_session_factory) -> CompiledStateGraph`, `QuizOutput` schema (tool args), `AgentContext` dataclass

- [ ] **Step 1: Delete EvaluationOutput from schemas.py**

Replace the entire `EvaluationOutput` class (lines 48-53) with nothing. The final `schemas.py` should end after `QuizOutput`:

```python
"""Agent 结构化输出 schema（Pydantic，非 SQLModel）。

present_question 工具的 args schema。从 tools.py 抽出，
使数据契约可独立 import/单测，不拖入 LightRAGClient 等工具依赖。
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuizOutput(BaseModel):
    """出题 LLM 的结构化输出 schema（present_question 工具 args）。"""

    q_type: Literal["single", "multi", "short"] = Field(description="题型：单选/多选/简答")
    stem: str = Field(description="题干")
    options: list[str] | None = Field(None, description="选项列表，short 题为 null")
    answer: str = Field(description="正确答案（single: 选项文本；multi: 'A,C,D'；short: 要点列表）")
    analysis: str = Field(description="题目解析")

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        """容错处理 LLM 返回的 options 格式。

        LLM 可能返回：
        - list[str]：正常
        - None：short 题无选项
        - str：可能是 JSON 编码的列表 '["A","B","C"]' 或单个选项文本
        - 其他：视为 None
        """
        if v is None:
            return None
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, str):
            import json as _json
            try:
                parsed = _json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
            return [v]
        return None
```

- [ ] **Step 2: Update test_agent_schemas.py - remove EvaluationOutput**

Replace `test_agent_schemas.py` with:

```python
"""agent.schemas 单元测试：QuizOutput._coerce_options 容错分支。

纯单元测试，无 DB/LightRAG/LLM 依赖。
"""
import pytest

from tutoring.agent.schemas import QuizOutput


def _make(**options_override) -> QuizOutput:
    data = {"q_type": "single", "stem": "q", "answer": "a", "analysis": "an"}
    data.update(options_override)
    return QuizOutput.model_validate(data)


def test_options_none():
    assert _make(options=None).options is None


def test_options_list_of_str():
    assert _make(options=["A", "B", "C"]).options == ["A", "B", "C"]


def test_options_list_coerces_non_str_items():
    assert _make(options=["A", 1, True]).options == ["A", "1", "True"]


def test_options_json_string_parsed():
    assert _make(options='["A","B","C"]').options == ["A", "B", "C"]


def test_options_bare_string_wrapped():
    assert _make(options="A").options == ["A"]


def test_options_invalid_json_string_wrapped():
    assert _make(options="[A,B").options == ["[A,B"]


def test_options_invalid_type_becomes_none():
    assert _make(options=123).options is None


def test_options_default_none_when_omitted():
    assert _make().options is None


def test_quiz_output_rejects_invalid_q_type():
    with pytest.raises(Exception):
        QuizOutput.model_validate(
            {"q_type": "invalid", "stem": "q", "answer": "a", "analysis": "an"}
        )
```

- [ ] **Step 3: Run schema unit tests**

Run: `uv run pytest tests/test_agent_schemas.py -v`
Expected: PASS (9 tests)

- [ ] **Step 4: Update prompts.py - merge quiz/eval rules into main prompt**

Replace `_CORE_PRINCIPLES` and `_AVAILABLE_TOOLS` and delete `QUIZ_GENERATION_PROMPT` + `EVALUATION_PROMPT`. The new `prompts.py` (lines 6-96 region) becomes:

```python
_CORE_PRINCIPLES = """## 核心原则
1. 绝不直接给出答案。通过提问引导学生自己推导出结论。
2. 当学生提问或讨论某个概念时，先调用 search_knowledge 检索相关知识，再基于检索内容设计追问。
3. 如果检索结果为空，告诉学生"这个问题可能超出当前课程知识库范围"，引导回课程内容。
4. 根据学生的回答判断理解程度：
   - 理解有误 -> 针对性追问，暴露矛盾
   - 理解部分 -> 追问未覆盖的部分
   - 理解到位 -> 调用 present_question 出题检验
5. 每次追问保持上下文连贯，不要突兀跳转话题。

## 出题与评估流程（极其重要）
当学生说"考考我"/"出题"/"测验"/"quiz"等任何表达想做题意图的话时，**必须**通过调用 present_question 工具出题，**禁止**自己在文本里写题目和选项然后让学生回答。

完整流程：
1. [可选] 先调 search_knowledge 检索相关知识作为出题素材
2. 在你的推理中设计题目：
   - 考察理解，不考死记硬背
   - 单选题 4 个选项；多选题 4-6 个选项；简答题无选项
   - 答案要明确：single 填选项完整文本（如 "TCP三次握手"）；multi 填 "A,C,D"；short 填要点
   - analysis 说明考点和正确答案的依据
3. 调用 present_question(topic, q_type, stem, options, answer, analysis)
4. 工具会暂停等待学生答题，学生提交后返回 {question_id, student_answer}
5. 拿到学生答案后，对比你传入的正确答案，自行评估：
   - 单选：完全匹配 = correct，否则 = wrong
   - 多选：全对 = correct，漏选无错选 = partial，有错选 = wrong
   - 简答：按要点命中评分，全部命中 = correct，部分 = partial，偏离 = wrong
6. 在回复中给学生反馈（对错 + 错因 + 正确答案 + 解析），继续苏格拉底式追问

只有在学生明确表示不想做题、或你在引导推导过程中需要反问时，才可以在文本中提问。这类反问是引导思考的追问，不是"考题"。"""

_AVAILABLE_TOOLS = """## 可用工具
- search_knowledge(query): 检索课程知识库（含知识图谱），返回相关知识片段
- present_question(topic, q_type, stem, options, answer, analysis): 向学生展示一道题并等待作答，返回学生答案"""
```

Delete the `QUIZ_GENERATION_PROMPT` and `EVALUATION_PROMPT` blocks entirely (original lines 54-96). The `# === AgentContext + @dynamic_prompt 中间件 ===` section and everything below stays unchanged.

- [ ] **Step 5: Rewrite tools.py - replace quiz_flow with present_question**

Replace the entire `tools.py` with:

```python
"""Agent 工具工厂：make_tools() 闭包注入依赖。

LangChain 1.x 模式：
- @tool 装饰器来自 langchain_core.tools
- interrupt() 来自 langgraph.types，实现 HITL 暂停
- RunnableConfig 用于访问 thread_id（= session_id）
- make_tools() 由 build_agent() 调用，闭包捕获 LightRAGClient + db_session_factory

工具内部零 LLM 调用——出题和评估全部由主智能体在推理中完成。
"""
import logging
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.db import repos
from tutoring.knowledge.client import LightRAGClient

logger = logging.getLogger(__name__)


def make_tools(
    *,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> list[BaseTool]:
    """构建 agent 工具列表，闭包捕获依赖。

    由 build_agent() 调用，测试可独立构造工具而无需碰全局态。
    """

    @asynccontextmanager
    async def _db_session():
        """工具内部获取 DB session 的异步上下文管理器。"""
        async with db_session_factory() as session:
            yield session

    @tool
    async def search_knowledge(query: str) -> str:
        """检索课程知识库（知识图谱 + RAG），返回相关知识片段。

        当学生提问或讨论某个概念时，先调用此工具检索相关知识，
        再基于检索内容设计苏格拉底式追问或出题。

        Args:
            query: 检索关键词，需包含完整上下文（消除代词指代）
        """
        try:
            result = await lightrag_client.query(
                query=query,
                mode="mix",
                only_need_context=True,
                include_references=True,
            )
        except Exception as e:
            logger.exception("search_knowledge 失败")
            return f"知识库检索失败: {e}"

        context = (result.get("response") or "").strip()
        if not context:
            return "未检索到相关内容，该问题可能超出当前课程知识库范围"
        return context

    @tool
    async def present_question(
        topic: str,
        q_type: Literal["single", "multi", "short"],
        stem: str,
        options: list[str] | None,
        answer: str,
        analysis: str,
        config: RunnableConfig,
    ) -> dict:
        """向学生展示一道题目并等待作答。

        在你推理生成题目内容后调用此工具。工具会：
        1. 将题目存入数据库
        2. 暂停等待学生答题（interrupt）
        3. 学生提交后返回其答案

        拿到学生答案后，请对比你传入的正确答案自行评估，
        在回复中给学生反馈（对错 + 错因 + 正确答案 + 解析）。

        Args:
            topic: 知识点名称，用于幂等去重和答题记录查询
            q_type: 题型（single/multi/short）
            stem: 题干文本
            options: 选项列表，简答题传 None
            answer: 正确答案（single: 选项文本；multi: "A,C,D"；short: 要点）
            analysis: 题目解析（考点 + 答案依据）
        """
        from langgraph.types import interrupt

        session_id = UUID(config["configurable"]["thread_id"])

        async with _db_session() as db_session:
            quiz = await repos.upsert_pending_question(
                db_session,
                session_id=session_id,
                topic=topic,
                q_type=q_type,
                stem=stem,
                options=options,
                answer=answer,
                analysis=analysis,
            )

        student_answer = interrupt(
            {
                "question_id": str(quiz.id),
                "topic": topic,
                "q_type": q_type,
                "stem": stem,
                "options": options,
            }
        )

        if student_answer.get("action") == "skip":
            async with _db_session() as db_session:
                await repos.update_question(db_session, quiz.id, status="skipped")
            return {"question_id": str(quiz.id), "action": "skipped"}

        user_answer = student_answer.get("answer", "")
        async with _db_session() as db_session:
            await repos.update_question(
                db_session,
                quiz.id,
                status="answered",
                user_answer=user_answer,
            )

        return {"question_id": str(quiz.id), "student_answer": user_answer}

    return [search_knowledge, present_question]
```

- [ ] **Step 6: Update factory.py - absorb make_tools() call**

Replace the entire `factory.py` with:

```python
from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tutoring.agent.llm import get_llm
from tutoring.agent.prompts import AgentContext, main_agent_system_prompt
from tutoring.agent.tools import make_tools
from tutoring.knowledge.client import LightRAGClient


def build_agent(
    checkpointer: BaseCheckpointSaver,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> CompiledStateGraph:
    """构建 agent。每次调用都新建实例。

    生产环境由 FastAPI lifespan 调用一次，进程内天然单例；
    测试环境每个 lifespan 重建后调用得到新实例，无需手动重置。

    Args:
        checkpointer: 已 .setup() 的 BaseCheckpointSaver 实例
            （如 AsyncPostgresSaver）
        lightrag_client: LightRAG 客户端单例
        db_session_factory: SQLAlchemy 异步 session factory

    Returns:
        CompiledStateGraph: 可用于 astream_events / aget_state 等
    """
    tools = make_tools(
        lightrag_client=lightrag_client,
        db_session_factory=db_session_factory,
    )
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 7: Update test_agent_tools.py - expect present_question**

Replace the entire `test_agent_tools.py` with:

```python
"""make_tools 工厂测试：替代原模块级 _state 隐式注入。"""
from tutoring.agent.tools import make_tools
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory
from tutoring.knowledge.client import LightRAGClient


async def test_make_tools_returns_expected_tools():
    lightrag = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    engine = create_engine(settings.database_url)
    tools = make_tools(
        lightrag_client=lightrag,
        db_session_factory=create_session_factory(engine),
    )
    assert [t.name for t in tools] == ["search_knowledge", "present_question"]
    await engine.dispose()
```

- [ ] **Step 8: Run agent unit + tools tests**

Run: `uv run pytest tests/test_agent_schemas.py tests/test_agent_tools.py -v`
Expected: PASS (9 schema tests + 1 tools test)

- [ ] **Step 9: Commit**

```bash
git add backend/src/tutoring/agent/schemas.py backend/src/tutoring/agent/prompts.py backend/src/tutoring/agent/tools.py backend/src/tutoring/agent/factory.py backend/tests/test_agent_schemas.py backend/tests/test_agent_tools.py
git commit -m "refactor: unify quiz flow into main agent reasoning

Replace quiz_flow sub-agent tool (2 isolated LLM calls) with thin
present_question tool (zero LLM calls). Main agent generates quiz
content as tool args and evaluates in its own response text.

- Delete EvaluationOutput schema, QUIZ_GENERATION_PROMPT, EVALUATION_PROMPT
- Merge quiz generation + evaluation rules into main system prompt
- build_agent() absorbs make_tools() call (new signature)
- present_question: DB persist + interrupt + return student answer only"
```

---

### Task 2: Migrate runtime.py to chat/sse.py + update main.py

**Files:**
- Delete: `backend/src/tutoring/agent/runtime.py`
- Modify: `backend/src/tutoring/chat/sse.py`
- Modify: `backend/src/tutoring/main.py`

**Interfaces:**
- Consumes: `CompiledStateGraph` (from `build_agent`), `AgentContext` (from `chat.service`)
- Produces: `chat/sse.py` with inline `stream_chat()` / `resume_quiz()` functions + SSE endpoints

- [ ] **Step 1: Rewrite chat/sse.py - absorb runtime functions**

Replace the entire `chat/sse.py` with:

```python
"""Chat SSE 端点 + 流式编排：send_message + quiz resume。

流式编排逻辑（原 agent/runtime.py）内联于此：
- agent.astream_events(version="v3") 返回 AsyncGraphRunStream 对象
- stream.messages -> 异步可迭代的消息对象；message.text -> 异步可迭代的 token
- stream.interrupted() -> awaitable bool（注意：是 async 方法，不是属性！）
- stream.interrupts() -> awaitable list[Interrupt]（同上）
- Command(resume=value) 从 interrupt 恢复
"""
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.agent.prompts import AgentContext
from tutoring.chat import service as chat_service
from tutoring.chat.schemas import QuizResumeRequest, SendMessageRequest
from tutoring.core.deps import CurrentUser, get_agent, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def stream_chat(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    user_msg: str,
    context: AgentContext,
    db_session: AsyncSession,
) -> AsyncIterator[str]:
    """首次发送消息 -> SSE 流。

    Yields SSE 格式字符串：
        event: text\\ndata: {...}\\n\\n
        event: quiz_interrupt\\ndata: {...}\\n\\n
        event: done\\ndata: {}\\n\\n
        event: error\\ndata: {...}\\n\\n
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    try:
        stream = await agent.astream_events(
            {"messages": [HumanMessage(content=user_msg)]},
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("stream_chat 失败")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def resume_quiz(
    agent: CompiledStateGraph,
    session_id: uuid.UUID,
    action: str,
    answer: str | None,
    db_session: AsyncSession,
    context: AgentContext,
) -> AsyncIterator[str]:
    """提交答题 -> SSE 流继续。

    Yields 同 stream_chat 的事件类型（resume 时不会有 quiz_interrupt）。

    runtime context 不进 checkpoint，resume 时必须像 stream_chat 一样重新传入，
    否则 main_agent_system_prompt 中间件读 context 会拿到 None。
    """
    config = {
        "configurable": {"thread_id": str(session_id)},
        "recursion_limit": 15,
    }
    resume_value: dict = {"action": action}
    if action == "answer":
        resume_value["answer"] = answer or ""

    try:
        stream = await agent.astream_events(
            Command(resume=resume_value),
            config=config,
            version="v3",
            context=context,
        )
        async for message in stream.messages:
            async for token in message.text:
                yield _sse("text", {"content": token})

        if await stream.interrupted():
            interrupts = await stream.interrupts()
            for it in interrupts:
                yield _sse("quiz_interrupt", it.value)
            yield _sse("done", {})
            return

        await _save_final_agent_message(agent, config, db_session, session_id)
        yield _sse("done", {})
    except Exception as e:
        logger.exception("resume_quiz 失败")
        yield _sse("error", {"message": str(e), "code": "AGENT_ERROR"})


async def _save_final_agent_message(
    agent: CompiledStateGraph, config: dict, db_session: AsyncSession, session_id: uuid.UUID
) -> None:
    """从 LangGraph state 取最终 AIMessage，持久化到 Message 表。

    LangChain 1.x 的 AIMessage.content 可能是：
    - str：纯文本
    - list[dict]：结构化内容块 [{"type":"text","text":"..."}, ...]
    需统一提取为纯文本字符串。
    """
    state = await agent.aget_state(config)
    messages = state.values.get("messages") or []
    if not messages:
        return
    final_msg = messages[-1]
    content = getattr(final_msg, "content", None)
    text = _extract_text(content)
    if text:
        await db.save_message(
            db_session, session_id=session_id, role="agent", content=text
        )


def _extract_text(content) -> str:
    """从 AIMessage.content 提取纯文本。

    处理两种格式：
    - str：直接返回
    - list[dict]：拼接所有 {"type":"text","text":"..."} 块
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _sse(event: str, data: dict) -> str:
    """格式化 SSE 帧。JSON 不转义非 ASCII（中文）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """发送消息，SSE 流式返回 agent 回复（event: text|quiz_interrupt|done|error）。"""
    sess = await chat_service.get_active_session(db_session, session_id, user.id)

    if await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_INTERRUPTED",
            "Session is paused at a quiz; call /quiz/resume first",
        )

    await db.save_message(
        db_session, session_id=session_id, role="user", content=body.content
    )
    await db.touch_session(db_session, session_id)

    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in stream_chat(
                agent, session_id, body.content, ctx, db_session
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/sessions/{session_id}/quiz/resume")
async def resume_quiz_endpoint(
    session_id: uuid.UUID,
    body: QuizResumeRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
    agent: CompiledStateGraph = Depends(get_agent),
):
    """提交答题（answer/skip），SSE 流式返回 agent 续接回复。"""
    sess = await chat_service.get_active_session(db_session, session_id, user.id)

    if not await chat_service.is_interrupted(agent, session_id):
        raise AppError(
            409, "SESSION_NOT_INTERRUPTED",
            "Session is not paused; no quiz to resume",
        )

    ctx = await chat_service.build_agent_context(db_session, sess)

    async def raw_stream() -> AsyncIterator[bytes]:
        try:
            async for sse_frame in resume_quiz(
                agent, session_id, body.action, body.answer, db_session, ctx
            ):
                yield sse_frame.encode("utf-8")
        finally:
            await db.touch_session(db_session, session_id)

    return StreamingResponse(
        raw_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 2: Delete agent/runtime.py**

Run: `rm backend/src/tutoring/agent/runtime.py`

- [ ] **Step 3: Update main.py - simplify build_agent call**

In `main.py`, replace the lifespan agent construction section (original lines 51-66):

```python
        # 4. 构建工具（闭包注入 LightRAGClient + DB session factory）
        from tutoring.agent.tools import make_tools
        tools = make_tools(
            lightrag_client=lightrag_client,
            db_session_factory=db_session_factory,
        )

        # 5. 构建 agent 单例
        app.state.agent = None
        try:
            from tutoring.agent.factory import build_agent
            app.state.agent = build_agent(checkpointer, tools)
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent 构建失败: %s", e)
            app.state.agent = None
```

with:

```python
        # 4. 构建 agent 单例（内部封装工具构造）
        app.state.agent = None
        try:
            from tutoring.agent.factory import build_agent
            app.state.agent = build_agent(
                checkpointer=checkpointer,
                lightrag_client=lightrag_client,
                db_session_factory=db_session_factory,
            )
            logger.info("Agent built")
        except Exception as e:
            logger.warning("Agent 构建失败: %s", e)
            app.state.agent = None
```

- [ ] **Step 4: Verify imports - app should start without ImportError**

Run: `uv run python -c "from tutoring.main import app; print('imports OK')"`
Expected: `imports OK` (no ImportError)

- [ ] **Step 5: Commit**

```bash
git add backend/src/tutoring/chat/sse.py backend/src/tutoring/main.py
git rm backend/src/tutoring/agent/runtime.py
git commit -m "refactor: migrate runtime.py to chat/sse.py, simplify build_agent call

- Move stream_chat/resume_quiz/SSE helpers from agent/runtime.py to chat/sse.py
- Delete agent/runtime.py (SSE/DB orchestration is backend concern, not AI)
- main.py: build_agent() now takes (checkpointer, lightrag_client, db_session_factory)
- agent module public API: build_agent() + AgentContext only"
```

---

### Task 3: Update integration tests

**Files:**
- Modify: `backend/tests/test_chat_streaming.py`

**Interfaces:**
- Consumes: working app with new `present_question` tool
- Produces: passing integration tests

- [ ] **Step 1: Update test_chat_streaming.py**

In `test_chat_streaming.py`, make three changes:

**Change 1**: In `test_quiz_hitl_full_flow` (line 85), update the prompt to not reference the old tool name:

Replace:
```python
        json={"content": "请使用 quiz_flow 工具考考我关于 HTTP 协议的知识"},
```
with:
```python
        json={"content": "请使用 present_question 工具考考我关于 HTTP 协议的知识"},
```

And replace the skip message (line 93):
```python
        pytest.skip("Agent 未触发 quiz_flow（LLM 输出不确定）")
```
with:
```python
        pytest.skip("Agent 未触发 present_question（LLM 输出不确定）")
```

**Change 2**: In `test_quiz_hitl_answer_flow` (line 130), update the prompt:

Replace:
```python
        json={"content": "请使用 quiz_flow 工具考考我关于网络分层模型的知识"},
```
with:
```python
        json={"content": "请使用 present_question 工具考考我关于网络分层模型的知识"},
```

And replace the skip message (line 138):
```python
        pytest.skip("Agent 未触发 quiz_flow（LLM 输出不确定）")
```
with:
```python
        pytest.skip("Agent 未触发 present_question（LLM 输出不确定）")
```

**Change 3**: In `test_quiz_hitl_answer_flow`, remove the verdict assertion (line 155). Replace:

```python
    assert q["user_answer"] == "这是我的测试答案"
    assert q["verdict"] in ("correct", "partial", "wrong")
    assert q["answered_at"] is not None
```

with:

```python
    assert q["user_answer"] == "这是我的测试答案"
    assert q["answered_at"] is not None
```

(verdict is no longer populated by a tool — the main agent evaluates in free text.)

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_chat_streaming.py -v`
Expected: PASS (4 tests: `test_free_mode_chat_streaming`, `test_resume_without_interrupt_fails`, `test_send_message_to_ended_session_fails`, `test_quiz_hitl_full_flow`). `test_quiz_hitl_answer_flow` may PASS or SKIP depending on LLM behavior.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS or SKIP (LLM-dependent quiz tests may skip)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_chat_streaming.py
git commit -m "test: update integration tests for unified agent quiz flow

- Update prompts to reference present_question instead of quiz_flow
- Remove verdict assertion (main agent evaluates in free text, not
  structured EvaluationOutput)"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ `present_question` tool (Task 1, Step 5)
- ✅ Delete `EvaluationOutput` (Task 1, Step 1)
- ✅ Delete `QUIZ_GENERATION_PROMPT` / `EVALUATION_PROMPT` (Task 1, Step 4)
- ✅ Merge quiz/eval rules into `_CORE_PRINCIPLES` (Task 1, Step 4)
- ✅ `build_agent()` absorbs `make_tools()` (Task 1, Step 6)
- ✅ Migrate `runtime.py` -> `chat/sse.py` (Task 2, Steps 1-2)
- ✅ Update `main.py` (Task 2, Step 3)
- ✅ Update tests (Task 1 Steps 2,7; Task 3)
- ✅ DB schema unchanged (no migration needed)
- ✅ SSE events unchanged
- ✅ Frontend unchanged

**2. Placeholder scan:** No TBD/TODO. All steps have complete code.

**3. Type consistency:**
- `present_question` returns `dict` in all code paths ✅
- `build_agent` signature: `(checkpointer, lightrag_client, db_session_factory)` consistent across factory.py and main.py ✅
- Tool names: `["search_knowledge", "present_question"]` consistent across tools.py and test ✅

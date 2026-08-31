from types import SimpleNamespace
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from teaching_agent.infrastructure.message_persistence import (
    _extract_turn,
    _has_knowledge_hit,
    MessagePersistenceMiddleware,
)


def _tool_result(tool_name: str, content: str = "ok") -> ToolMessage:
    return ToolMessage(content=content, name=tool_name, tool_call_id="t1")


# === _extract_turn ===


def test_extract_turn_picks_latest_student_and_final_ai():
    messages = [
        HumanMessage(content="第一问"),
        AIMessage(content="第一答"),
        HumanMessage(content="第二问"),
        AIMessage(content="第二答"),
    ]
    student, ai = _extract_turn(messages)
    assert student == "第二问"
    assert ai == "第二答"


def test_extract_turn_skips_tool_call_ai_message():
    messages = [
        HumanMessage(content="问"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "x"}, "id": "1"}],
        ),
        _tool_result("search_knowledge"),
        AIMessage(content="最终回复"),
    ]
    student, ai = _extract_turn(messages)
    assert student == "问"
    assert ai == "最终回复"


def test_extract_turn_empty_messages():
    assert _extract_turn([]) == (None, None)


def test_extract_turn_handles_list_content():
    messages = [
        HumanMessage(content=[{"type": "text", "text": "多模态"}, {"type": "text", "text": "提问"}]),
        AIMessage(content=[{"type": "text", "text": "多模态回复"}]),
    ]
    student, ai = _extract_turn(messages)
    assert student == "多模态提问"
    assert ai == "多模态回复"


# === _has_knowledge_hit ===


def test_has_knowledge_hit_true_in_current_turn():
    messages = [
        HumanMessage(content="上轮问题"),
        AIMessage(content="上轮回复"),
        HumanMessage(content="本轮问题"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "x"}, "id": "2"}],
        ),
        _tool_result("search_knowledge"),
        AIMessage(content="本轮回复"),
    ]
    assert _has_knowledge_hit(messages) is True


def test_has_knowledge_hit_true_when_tool_result_present():
    messages = [
        HumanMessage(content="问"),
        _tool_result("search_knowledge"),
        AIMessage(content="答"),
    ]
    assert _has_knowledge_hit(messages) is True


def test_has_knowledge_hit_false_when_only_history_hit():
    messages = [
        HumanMessage(content="上轮问题"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "x"}, "id": "1"}],
        ),
        _tool_result("search_knowledge"),
        AIMessage(content="上轮回复"),
        HumanMessage(content="本轮问题"),
        AIMessage(content="本轮回复"),
    ]
    assert _has_knowledge_hit(messages) is False


def test_has_knowledge_hit_false_without_any_call():
    messages = [HumanMessage(content="问"), AIMessage(content="答")]
    assert _has_knowledge_hit(messages) is False


# === MessagePersistenceMiddleware.aafter_agent ===


@pytest.mark.asyncio
async def test_middleware_persists_current_turn(monkeypatch):
    captured = {}

    async def fake_persist(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "teaching_agent.infrastructure.message_persistence._persist", fake_persist
    )
    runtime = SimpleNamespace(execution_info=SimpleNamespace(thread_id="3f5b1a4e-0000-0000-0000-000000000001"))
    state = {"messages": [HumanMessage(content="问"), AIMessage(content="答")]}

    result = await MessagePersistenceMiddleware().aafter_agent(state, runtime)

    assert result is None
    assert captured["session_id"] == UUID("3f5b1a4e-0000-0000-0000-000000000001")
    assert captured["student_content"] == "问"
    assert captured["ai_content"] == "答"
    assert captured["knowledge_hit"] is False


@pytest.mark.asyncio
async def test_middleware_marks_knowledge_hit(monkeypatch):
    captured = {}

    async def fake_persist(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "teaching_agent.infrastructure.message_persistence._persist", fake_persist
    )
    runtime = SimpleNamespace(execution_info=SimpleNamespace(thread_id="3f5b1a4e-0000-0000-0000-000000000002"))
    state = {
        "messages": [
            HumanMessage(content="问"),
            AIMessage(content="", tool_calls=[{"name": "search_knowledge", "args": {}, "id": "1"}]),
            _tool_result("search_knowledge"),
            AIMessage(content="答"),
        ]
    }

    await MessagePersistenceMiddleware().aafter_agent(state, runtime)

    assert captured["knowledge_hit"] is True


@pytest.mark.asyncio
async def test_middleware_skips_without_thread_id(monkeypatch):
    called = []

    async def fake_persist(**kwargs):
        called.append(kwargs)

    monkeypatch.setattr(
        "teaching_agent.infrastructure.message_persistence._persist", fake_persist
    )
    runtime = SimpleNamespace(execution_info=None)
    state = {"messages": [HumanMessage(content="问"), AIMessage(content="答")]}

    await MessagePersistenceMiddleware().aafter_agent(state, runtime)

    assert called == []


@pytest.mark.asyncio
async def test_middleware_swallows_persistence_errors(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("api server down")

    monkeypatch.setattr(
        "teaching_agent.infrastructure.message_persistence._persist", boom
    )
    runtime = SimpleNamespace(execution_info=SimpleNamespace(thread_id="3f5b1a4e-0000-0000-0000-000000000003"))
    state = {"messages": [HumanMessage(content="问"), AIMessage(content="答")]}

    # 不应向外抛异常
    result = await MessagePersistenceMiddleware().aafter_agent(state, runtime)

    assert result is None

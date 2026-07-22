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

"""会话历史重建（读侧）。

LangGraph 把整段对话存在 checkpoint 里，build_history 读取这些原始消息，
还原成前端可渲染的 item 列表，并附带"当前是否有未答 quiz"和"是否正在处理"。
"""
import json
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from tutoring.chat import tasks
from tutoring.chat.streaming import iter_tool_calls, stream_config


async def build_history(
    agent: CompiledStateGraph, session_id: uuid.UUID
) -> dict:
    """重建会话历史：item 列表 + pending_quiz + processing 标志。"""
    config = stream_config(session_id)
    state = await agent.aget_state(config)

    items = _extract_items(state.values.get("messages") or [])
    pending_quiz = _extract_pending_quiz(state)
    processing = bool(tasks.get(session_id))

    return {"items": items, "pending_quiz": pending_quiz, "processing": processing}


# === item 提取 ===


def _extract_items(messages: list) -> list[dict]:
    """把 LangGraph 原始消息序列还原成前端 item 列表。

    三种消息各自处理：
    - HumanMessage -> user item
    - AIMessage -> 可能含 tool_calls：普通工具 -> tool_call item；
      present_question -> quiz item（标记 pending，等待对应 ToolMessage 回填）；
      文本部分 -> agent item
    - ToolMessage -> present_question 的返回值，回填之前那个 quiz item 的
      状态（skipped / answered）和 quiz_id
    """
    items: list[dict] = []
    pending_quizzes: list[int] = []  # 等待 ToolMessage 回填的 quiz item 下标

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


def _collect_ai_message(
    msg: AIMessage, items: list[dict], pending_quizzes: list[int]
) -> None:
    for name, args in iter_tool_calls(msg):
        if name == "present_question":
            items.append(_build_quiz_item(args))
            pending_quizzes.append(len(items) - 1)
        elif name:
            items.append({"type": "tool_call", "tool_name": name, "tool_input": args})
    if msg.text:
        items.append({"type": "agent", "content": msg.text})


def _apply_tool_result(
    msg: ToolMessage, items: list[dict], pending_quizzes: list[int]
) -> None:
    """present_question 的返回值回填到对应的 quiz item。

    因为 present_question 会 interrupt 暂停整图，pending 队列里等待的下一个
    quiz 一定对应此刻到达的这条 ToolMessage，故按 FIFO pop(0)。
    """
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


def _build_quiz_item(args: dict) -> dict:
    """从 present_question 的入参构造一个 pending quiz item。"""
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
    """options 防御性规整：LLM 偶尔把 list 编码成 JSON 字符串。"""
    if isinstance(raw_options, str):
        try:
            raw_options = json.loads(raw_options)
        except (json.JSONDecodeError, TypeError):
            return [raw_options]
    return raw_options or []


def _parse_tool_result(content_str: str) -> dict:
    """解析 ToolMessage 内容为 dict；非 JSON 返回空 dict。"""
    try:
        return json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_pending_quiz(state) -> dict | None:
    """从 checkpoint state 里取出当前未答 quiz 的 interrupt 值。"""
    if not state.next:
        return None
    for task in state.tasks:
        for intr in getattr(task, "interrupts", None) or []:
            if hasattr(intr, "value"):
                return intr.value
    return None

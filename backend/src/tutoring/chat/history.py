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


def _extract_pending_quiz(state: dict) -> dict | None:
    """从 Server state（dict）取当前未答 quiz 的 interrupt 值。"""
    if not state.get("next"):
        return None
    for task in state.get("tasks") or []:
        for intr in task.get("interrupts") or []:
            if "value" in intr:
                return intr["value"]
    return None

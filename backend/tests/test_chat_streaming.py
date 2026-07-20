"""端到端 chat 流式 + HITL quiz 全流程测试。

真实 LLM（qwen3.6-flash）+ 真实 LightRAG + 真实 DB。
LLM 输出不确定，quiz_flow 触发用 pytest.skip 处理。
"""
import json


def parse_sse_stream(resp_bytes: bytes) -> list[dict]:
    """解析 SSE 字节流为 {event, data} 列表。"""
    events = []
    text = resp_bytes.decode("utf-8")
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event_type:
            events.append({"event": event_type, "data": data})
    return events


async def test_free_mode_chat_streaming(client, cleanup_db):
    """free 模式 SSE 流式：发消息 -> text tokens -> done。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "什么是 TCP 三次握手？"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert any(e["event"] == "text" for e in events), "应有 text 事件"
    assert events[-1]["event"] == "done", "应以 done 结束"

    # 验证消息已落库
    resp = await client.get(f"/sessions/{sid}/messages")
    msgs = resp.json()
    assert len(msgs) >= 2  # user + agent
    assert msgs[0]["role"] == "user"
    assert msgs[-1]["role"] == "agent"


async def test_resume_without_interrupt_fails(client, cleanup_db):
    """无 interrupt 时调 resume -> 409。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "skip"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_INTERRUPTED"


async def test_send_message_to_ended_session_fails(client, cleanup_db):
    """ended session 发消息 -> 409。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]
    await client.delete(f"/sessions/{sid}")

    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "hello"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "SESSION_ENDED"


async def test_quiz_hitl_full_flow(client, cleanup_db):
    """quiz HITL 全流程：出题 -> interrupt -> resume(skip) -> question 状态更新。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    # 触发 quiz
    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "请使用 present_question 工具考考我关于 HTTP 协议的知识"},
    )
    events = parse_sse_stream(resp.content)
    quiz_events = [e for e in events if e["event"] == "quiz_interrupt"]

    if not quiz_events:
        import pytest

        pytest.skip("Agent 未触发 present_question（LLM 输出不确定）")

    quiz_payload = quiz_events[0]["data"]
    assert "question_id" in quiz_payload
    assert "q_type" in quiz_payload
    assert "stem" in quiz_payload

    # 验证 pending question 在 DB
    resp = await client.get(f"/sessions/{sid}/questions?status=pending")
    qs = resp.json()
    assert len(qs) == 1
    assert qs[0]["status"] == "pending"

    # resume with skip
    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "skip"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert events[-1]["event"] == "done"

    # 验证 question 状态更新为 skipped
    resp = await client.get(f"/sessions/{sid}/questions")
    qs = resp.json()
    skipped = [q for q in qs if q["id"] == quiz_payload["question_id"]]
    assert skipped
    assert skipped[0]["status"] == "skipped"


async def test_quiz_hitl_answer_flow(client, cleanup_db):
    """quiz HITL 答题流程：出题 -> interrupt -> resume(answer) -> 评估落库。"""
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "请使用 present_question 工具考考我关于网络分层模型的知识"},
    )
    events = parse_sse_stream(resp.content)
    quiz_events = [e for e in events if e["event"] == "quiz_interrupt"]

    if not quiz_events:
        import pytest

        pytest.skip("Agent 未触发 present_question（LLM 输出不确定）")

    # 提交答案
    resp = await client.post(
        f"/chat/sessions/{sid}/quiz/resume",
        json={"action": "answer", "answer": "这是我的测试答案"},
    )
    assert resp.status_code == 200
    events = parse_sse_stream(resp.content)
    assert events[-1]["event"] == "done"

    # 验证 question 已更新
    resp = await client.get(f"/sessions/{sid}/questions?status=answered")
    qs = resp.json()
    assert len(qs) == 1
    q = qs[0]
    assert q["user_answer"] == "这是我的测试答案"
    assert q["answered_at"] is not None

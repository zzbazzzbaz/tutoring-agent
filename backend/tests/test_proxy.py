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

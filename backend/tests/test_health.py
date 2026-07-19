"""健康检查端点测试。"""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["components"]["database"] == "ok"
    assert data["components"]["lightrag"] == "ok"
    assert data["components"]["agent"] == "ready"
    assert "langchain" in data["versions"]
    assert "langgraph" in data["versions"]

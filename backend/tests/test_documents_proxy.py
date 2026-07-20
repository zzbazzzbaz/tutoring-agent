"""LightRAG 代理端点测试。"""


async def test_pipeline_status(client):
    resp = await client.get("/documents/pipeline_status")
    assert resp.status_code == 200
    data = resp.json()
    assert "busy" in data


async def test_list_documents(client):
    resp = await client.post("/documents/paginated", json={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert "pagination" in data


async def test_graph_labels(client):
    resp = await client.get("/graph/label/list")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_graph_popular_labels(client):
    resp = await client.get("/graph/label/popular?limit=5")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) <= 5


async def test_graph_search_labels(client):
    resp = await client.get("/graph/label/search?query=TCP")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

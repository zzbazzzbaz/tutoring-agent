"""Sessions CRUD 测试。"""


async def test_create_free_session(client, cleanup_db):
    resp = await client.post("/sessions", json={"mode": "free"})
    assert resp.status_code == 201
    sess = resp.json()
    assert sess["mode"] == "free"
    assert sess["status"] == "active"
    assert sess["user_id"] == "demo-student"


async def test_create_project_session_requires_published_project(client, cleanup_db):
    # 创建 draft project
    resp = await client.post(
        "/projects",
        json={"name": "Draft", "background_md": "test", "status": "draft"},
    )
    pid = resp.json()["id"]

    # 尝试创建 project session -> 422
    resp = await client.post("/sessions", json={"mode": "project", "project_id": pid})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "PROJECT_NOT_PUBLISHED"

    # 发布后重试
    await client.patch(f"/projects/{pid}", json={"status": "published"})
    resp = await client.post("/sessions", json={"mode": "project", "project_id": pid})
    assert resp.status_code == 201
    assert resp.json()["mode"] == "project"
    assert resp.json()["project_name"] == "Draft"


async def test_list_sessions_by_user(client, cleanup_db):
    # 创建 2 个 session
    await client.post("/sessions", json={"mode": "free"})
    await client.post("/sessions", json={"mode": "free"})

    # 列出
    resp = await client.get("/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 不同用户看不到
    resp = await client.get("/sessions", headers={"X-User-Id": "other-user"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_end_session(client, cleanup_db):
    resp = await client.post("/sessions", json={"mode": "free"})
    sid = resp.json()["id"]

    resp = await client.delete(f"/sessions/{sid}")
    assert resp.status_code == 204

    resp = await client.get(f"/sessions/{sid}")
    assert resp.json()["status"] == "ended"


async def test_session_not_found(client, cleanup_db):
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/sessions/{fake_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_FOUND"

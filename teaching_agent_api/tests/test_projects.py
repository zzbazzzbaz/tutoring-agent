"""Projects CRUD 测试。"""


async def test_project_crud(client, cleanup_db):
    # 创建 draft project
    resp = await client.post(
        "/projects",
        json={
            "name": "Test Project",
            "background_md": "# Test\n\nProject background",
            "status": "draft",
        },
    )
    assert resp.status_code == 201
    proj = resp.json()
    assert proj["status"] == "draft"
    pid = proj["id"]

    # 列出
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert any(p["id"] == pid for p in resp.json())

    # 查询单个
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"

    # 更新为 published
    resp = await client.patch(f"/projects/{pid}", json={"status": "published"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # 删除
    resp = await client.delete(f"/projects/{pid}")
    assert resp.status_code == 204

    # 查询 -> 404
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_project_name_conflict(client, cleanup_db):
    # 创建第一个
    resp = await client.post(
        "/projects", json={"name": "Unique", "background_md": "x", "status": "draft"}
    )
    assert resp.status_code == 201

    # 同名再创建 -> 409
    resp = await client.post(
        "/projects", json={"name": "Unique", "background_md": "x", "status": "draft"}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "PROJECT_NAME_CONFLICT"

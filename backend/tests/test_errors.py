"""统一错误格式测试。"""
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tutoring.core.errors import (
    AppError,
    LightRAGError,
    register_exception_handlers,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def app_error():
        raise AppError(404, "SESSION_NOT_FOUND", "Session abc not found")

    @app.get("/lightrag-error")
    async def lightrag_error():
        raise LightRAGError("connection refused")

    return app


async def test_app_error_format():
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        resp = await c.get("/app-error")
    assert resp.status_code == 404
    assert resp.json() == {
        "detail": {"error": {"code": "SESSION_NOT_FOUND", "message": "Session abc not found"}}
    }


async def test_lightrag_error_format():
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        resp = await c.get("/lightrag-error")
    assert resp.status_code == 502
    assert resp.json() == {
        "detail": {"error": {"code": "LIGHTRAG_ERROR", "message": "connection refused"}}
    }


async def test_api_404_format_unchanged(client):
    """契约回归：真实 API 的 404 保持 detail 包裹格式。"""
    resp = await client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"

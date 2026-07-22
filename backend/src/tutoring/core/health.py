import httpx
from fastapi import APIRouter, Request

from tutoring.core.config import settings

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    components = {"database": "unknown", "langgraph_server": "unknown"}

    # DB 检查
    try:
        from sqlalchemy import text
        async with request.app.state.db_session_factory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "fail"

    # LangGraph Server 检查（agent/rag 现由 Server 托管）
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{settings.langgraph_server_url.rstrip('/')}/ok")
            components["langgraph_server"] = "ok" if resp.status_code == 200 else "fail"
    except Exception:
        components["langgraph_server"] = "fail"

    import langchain
    from importlib.metadata import version as pkg_version
    return {
        "status": "healthy" if all(v == "ok" for v in components.values()) else "degraded",
        "components": components,
        "versions": {
            "api": "0.2.0",
            "langchain": langchain.__version__,
            "langgraph": pkg_version("langgraph"),
            "lightrag": pkg_version("lightrag-hku"),
        },
    }

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    components = {"database": "ok", "lightrag": "unknown", "agent": "unknown"}

    # DB 检查
    try:
        from sqlalchemy import text
        async with request.app.state.db_session_factory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "fail"

    # LightRAG 检查
    try:
        rag = request.app.state.rag
        components["lightrag"] = "ready" if rag is not None else "not_initialized"
    except Exception:
        components["lightrag"] = "fail"

    # Agent 检查
    try:
        agent = request.app.state.agent
        components["agent"] = "ready" if agent is not None else "not_built"
    except Exception:
        components["agent"] = "fail"

    import langchain
    from importlib.metadata import version as pkg_version
    return {
        "status": "healthy" if all(v in ("ok", "ready") for v in components.values()) else "degraded",
        "components": components,
        "versions": {
            "api": "0.2.0",
            "langchain": langchain.__version__,
            "langgraph": pkg_version("langgraph"),
            "lightrag": pkg_version("lightrag-hku"),
        },
    }

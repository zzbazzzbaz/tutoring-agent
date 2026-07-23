from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    components = {"database": "unknown"}

    # DB 检查
    try:
        from sqlalchemy import text

        async with request.app.state.db_session_factory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "fail"

    return {
        "status": "healthy" if all(v == "ok" for v in components.values()) else "degraded",
        "components": components,
        "versions": {"api": "0.2.0"},
    }

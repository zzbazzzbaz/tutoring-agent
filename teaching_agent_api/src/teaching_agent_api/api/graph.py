"""LightRAG 知识图谱代理端点。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from teaching_agent_api.deps import get_lightrag_client
from teaching_agent_api.lightrag.client import LightRAGClient

router = APIRouter(tags=["graph"])


@router.get("/graph/label/list")
async def list_labels(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> list[str]:
    try:
        return await lightrag.list_labels()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/graph/label/popular")
async def popular_labels(
    limit: int = Query(300, ge=1, le=1000),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    try:
        return await lightrag.popular_labels(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/graph/label/search")
async def search_labels(
    query: str = Query(..., min_length=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    try:
        return await lightrag.search_labels(query=query)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/graphs")
async def get_graph(
    label: str = Query(..., min_length=1),
    max_depth: int = Query(3, ge=1),
    max_nodes: int = Query(1000, ge=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    try:
        return await lightrag.get_graph(label=label, max_depth=max_depth, max_nodes=max_nodes)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )

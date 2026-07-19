"""LightRAG 代理端点（documents + graph 合并）。

纯透传，无业务逻辑。注入 X-API-Key 头（前端不知道 key），转发
multipart/JSON body，透传响应。上游错误由全局 handler 统一转 502。
"""
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File

from tutoring.core.deps import get_lightrag_client
from tutoring.knowledge.client import LightRAGClient

router = APIRouter(tags=["knowledge"])


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    content = await file.read()
    return await lightrag.upload_file(
        content, file.filename or "unknown", file.content_type or "application/octet-stream"
    )


@router.post("/documents/text")
async def insert_text(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.insert_text(await request.json())


@router.post("/documents/texts")
async def insert_texts(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.insert_texts(await request.json())


@router.post("/documents/scan")
async def scan(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.scan()


@router.get("/documents/track_status/{track_id}")
async def track_status(
    track_id: str,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.track_status(track_id)


@router.get("/documents/pipeline_status")
async def pipeline_status(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.pipeline_status()


@router.get("/documents/status_counts")
async def status_counts(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.status_counts()


@router.post("/documents/paginated")
async def list_documents(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.list_documents(await request.json())


@router.delete("/documents/delete_document")
async def delete_documents(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.delete_documents(await request.json())


@router.get("/graph/label/list")
async def list_labels(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> list[str]:
    return await lightrag.list_labels()


@router.get("/graph/label/popular")
async def popular_labels(
    limit: int = Query(300, ge=1, le=1000),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    return await lightrag.popular_labels(limit=limit)


@router.get("/graph/label/search")
async def search_labels(
    query: str = Query(..., min_length=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> list[str]:
    return await lightrag.search_labels(query=query)


@router.get("/graphs")
async def get_graph(
    label: str = Query(..., min_length=1),
    max_depth: int = Query(3, ge=1),
    max_nodes: int = Query(1000, ge=1),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    return await lightrag.get_graph(label=label, max_depth=max_depth, max_nodes=max_nodes)

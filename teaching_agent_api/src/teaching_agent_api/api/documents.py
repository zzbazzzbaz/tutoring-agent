"""LightRAG 文档代理端点。纯透传，无业务逻辑。

注入 X-API-Key 头（前端不知道 key），转发 multipart/JSON body，
透传响应（状态码 + body）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from teaching_agent_api.deps import get_lightrag_client
from teaching_agent_api.lightrag.client import LightRAGClient

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    content = await file.read()
    try:
        return await lightrag.upload_file(
            content, file.filename or "unknown", file.content_type or "application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.post("/text")
async def insert_text(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    body = await request.json()
    try:
        return await lightrag.insert_text(body)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.post("/texts")
async def insert_texts(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    body = await request.json()
    try:
        return await lightrag.insert_texts(body)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.post("/scan")
async def scan(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    try:
        return await lightrag.scan()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/track_status/{track_id}")
async def track_status(
    track_id: str,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    try:
        return await lightrag.track_status(track_id)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/pipeline_status")
async def pipeline_status(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    try:
        return await lightrag.pipeline_status()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.get("/status_counts")
async def status_counts(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    try:
        return await lightrag.status_counts()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.post("/paginated")
async def list_documents(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    body = await request.json()
    try:
        return await lightrag.list_documents(body)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )


@router.delete("/delete_document")
async def delete_documents(
    request: Request,
    lightrag: LightRAGClient = Depends(get_lightrag_client),
) -> dict:
    body = await request.json()
    try:
        return await lightrag.delete_documents(body)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "LIGHTRAG_ERROR", "message": str(e)}},
        )

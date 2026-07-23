from fastapi import APIRouter, Depends, File, Query, UploadFile

from tutoring.core.deps import CurrentUser, get_current_user
from tutoring.core.errors import AppError
from tutoring.lightrag import service as lightrag_service
from tutoring.lightrag.schemas import DeleteDocumentRequest, DocumentsRequest

router = APIRouter(prefix="/lightrag", tags=["lightrag"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可执行此操作")


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_teacher(user)
    content = await file.read()
    return await lightrag_service.upload_file(
        "/documents/upload",
        file.filename or "upload.bin",
        content,
        file.content_type or "application/octet-stream",
    )


@router.post("/documents/paginated")
async def list_documents(
    body: DocumentsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_teacher(user)
    return await lightrag_service.post_json("/documents/paginated", body.model_dump())


@router.get("/documents/status_counts")
async def status_counts(user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_teacher(user)
    return await lightrag_service.get_json("/documents/status_counts")


@router.get("/documents/pipeline_status")
async def pipeline_status(user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_teacher(user)
    return await lightrag_service.get_json("/documents/pipeline_status")


@router.get("/documents/track_status/{track_id}")
async def track_status(
    track_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_teacher(user)
    return await lightrag_service.get_json(f"/documents/track_status/{track_id}")


@router.delete("/documents/delete_document")
async def delete_document(
    body: DeleteDocumentRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_teacher(user)
    payload = body.model_dump()
    payload["delete_file"] = True
    return await lightrag_service.delete_json("/documents/delete_document", payload)


@router.get("/graph/label/popular")
async def popular_labels(
    limit: int = Query(default=300, ge=1, le=1000),
    user: CurrentUser = Depends(get_current_user),
) -> dict | list:
    _require_teacher(user)
    return await lightrag_service.get_json("/graph/label/popular", {"limit": limit})


@router.get("/graph/label/search")
async def search_labels(
    q: str,
    limit: int = Query(default=50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> dict | list:
    _require_teacher(user)
    return await lightrag_service.get_json("/graph/label/search", {"q": q, "limit": limit})


@router.get("/graphs")
async def get_graph(
    label: str,
    max_depth: int = Query(default=3, ge=1, le=10),
    max_nodes: int = Query(default=1000, ge=1, le=5000),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_teacher(user)
    return await lightrag_service.get_json(
        "/graphs",
        {"label": label, "max_depth": max_depth, "max_nodes": max_nodes},
    )

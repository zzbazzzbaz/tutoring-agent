from uuid import uuid4

import pytest

from tutoring.core.deps import CurrentUser
from tutoring.core.errors import AppError
from tutoring.lightrag import router as lightrag_router
from tutoring.lightrag.schemas import DeleteDocumentRequest, DocumentsRequest


def _teacher() -> CurrentUser:
    return CurrentUser(id=uuid4(), username="teacher", role="teacher", name="Teacher")


def _student() -> CurrentUser:
    return CurrentUser(id=uuid4(), username="student", role="student", name="Student")


@pytest.mark.asyncio
async def test_lightrag_routes_require_teacher():
    with pytest.raises(AppError) as exc:
        await lightrag_router.list_documents(DocumentsRequest(), user=_student())
    assert exc.value.status_code == 403
    assert exc.value.code == "TEACHER_ONLY"


@pytest.mark.asyncio
async def test_list_documents_forwards_paginated_request(monkeypatch):
    async def fake_post_json(path: str, payload: dict):
        assert path == "/documents/paginated"
        assert payload["page"] == 2
        assert payload["page_size"] == 10
        return {"items": [], "total": 0, "page": 2, "page_size": 10}

    monkeypatch.setattr(lightrag_router.lightrag_service, "post_json", fake_post_json)
    result = await lightrag_router.list_documents(
        DocumentsRequest(page=2, page_size=10), user=_teacher()
    )
    assert result["page"] == 2


@pytest.mark.asyncio
async def test_delete_document_forces_delete_file(monkeypatch):
    async def fake_delete_json(path: str, payload: dict):
        assert path == "/documents/delete_document"
        assert payload == {
            "doc_ids": ["doc-1"],
            "delete_file": True,
            "delete_llm_cache": False,
        }
        return {"status": "deletion_started", "message": "started", "doc_id": "doc-1"}

    monkeypatch.setattr(lightrag_router.lightrag_service, "delete_json", fake_delete_json)
    result = await lightrag_router.delete_document(
        DeleteDocumentRequest(doc_ids=["doc-1"]), user=_teacher()
    )
    assert result["status"] == "deletion_started"


@pytest.mark.asyncio
async def test_graph_forwards_query_params(monkeypatch):
    async def fake_get_json(path: str, params: dict | None = None):
        assert path == "/graphs"
        assert params == {"label": "AI", "max_depth": 2, "max_nodes": 200}
        return {"nodes": [], "edges": []}

    monkeypatch.setattr(lightrag_router.lightrag_service, "get_json", fake_get_json)
    result = await lightrag_router.get_graph(
        label="AI", max_depth=2, max_nodes=200, user=_teacher()
    )
    assert result == {"nodes": [], "edges": []}

# LightRAG Knowledge Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a teacher-only global knowledge-base management area that proxies LightRAG document and graph APIs through the business FastAPI backend.

**Architecture:** The frontend calls only `services/api_server` endpoints under `/lightrag/*`; the business backend enforces teacher-only access and forwards to LightRAG at `LIGHTRAG_BASE_URL` with `httpx`. The teacher management UI adds `/teacher/manage/knowledge` with document upload/list/status/delete and a graph viewer adapted from the existing LightRAG WebUI Sigma/Graphology implementation.

**Tech Stack:** FastAPI, httpx, Pydantic, pytest, Next.js 15, React 19, TypeScript 5.8, Tailwind, Sigma.js, Graphology.

## Global Constraints

- Use the recommended backend proxy approach; frontend must not call `http://localhost:19621` directly.
- Knowledge base scope is global for teacher users, not project-scoped.
- Every backend `/lightrag/*` route must require authenticated teacher users.
- Do not add a generic catch-all proxy; expose only the required LightRAG endpoints.
- Document deletion from the UI must send `delete_file: true` so LightRAG deletes the file and associated chunks/entities/relations.
- Preserve the current teacher management layout and component style.
- Reuse the LightRAG WebUI graph approach from `docs/_chat/LightRAG/lightrag_webui`.
- Keep unrelated untracked files, especially root `README.md`, out of commits unless explicitly requested.

---

## File Structure

- Create `services/api_server/src/tutoring/lightrag/__init__.py`: package marker.
- Create `services/api_server/src/tutoring/lightrag/schemas.py`: proxy request models.
- Create `services/api_server/src/tutoring/lightrag/service.py`: `httpx` forwarding helpers.
- Create `services/api_server/src/tutoring/lightrag/router.py`: teacher-only `/lightrag/*` router.
- Modify `services/api_server/src/tutoring/core/config.py`: add `lightrag_base_url`, `lightrag_api_key`, `lightrag_timeout_seconds`.
- Modify `services/api_server/src/tutoring/app.py`: include LightRAG router.
- Create `services/api_server/tests/test_lightrag_proxy.py`: backend contract tests with mocked service helpers.
- Modify `frontend/package.json`: add graph dependencies from LightRAG WebUI.
- Modify `frontend/src/components/layout/ManagementLayout.tsx`: add `知识库` teacher nav entry.
- Modify `frontend/src/lib/types.ts`: add LightRAG document/status/graph types.
- Create `frontend/src/lib/api/lightrag.ts`: frontend API client for backend proxy.
- Create `frontend/src/app/teacher/manage/knowledge/page.tsx`: route entry.
- Create `frontend/src/components/knowledge/KnowledgeBasePage.tsx`: page coordinator.
- Create `frontend/src/components/knowledge/KnowledgeUpload.tsx`: upload UI.
- Create `frontend/src/components/knowledge/KnowledgeDocumentTable.tsx`: document listing and deletion.
- Create `frontend/src/components/knowledge/KnowledgePipelineStatus.tsx`: pipeline/status counts panel.
- Create `frontend/src/components/knowledge/KnowledgeGraphPanel.tsx`: labels/search/graph wrapper.
- Create `frontend/src/components/knowledge/graph/GraphViewer.tsx`: adapted Sigma/Graphology viewer.
- Create `frontend/src/components/knowledge/graph/graphAdapter.ts`: LightRAG graph payload adapter.
- Create `frontend/src/components/knowledge/graph/types.ts`: graph-specific TS types.

---

### Task 1: Backend Proxy Contract Tests

**Files:**
- Create: `services/api_server/tests/test_lightrag_proxy.py`

**Interfaces:**
- Consumes: existing `CurrentUser` and `AppError`.
- Produces: failing expectations for `tutoring.lightrag.router` and `tutoring.lightrag.schemas`.

- [ ] **Step 1: Write failing tests**

Create `services/api_server/tests/test_lightrag_proxy.py`:

```python
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
```

- [ ] **Step 2: Verify red**

Run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/api_server"
uv run pytest tests/test_lightrag_proxy.py -q
```

Expected: import failure for missing `tutoring.lightrag`.

- [ ] **Step 3: Commit red tests**

```bash
git add services/api_server/tests/test_lightrag_proxy.py
git commit -m "test: add lightrag proxy contract tests"
```

---

### Task 2: Backend Proxy Implementation

**Files:**
- Create: `services/api_server/src/tutoring/lightrag/__init__.py`
- Create: `services/api_server/src/tutoring/lightrag/schemas.py`
- Create: `services/api_server/src/tutoring/lightrag/service.py`
- Create: `services/api_server/src/tutoring/lightrag/router.py`
- Modify: `services/api_server/src/tutoring/core/config.py`
- Modify: `services/api_server/src/tutoring/app.py`
- Test: `services/api_server/tests/test_lightrag_proxy.py`

**Interfaces:**
- Produces backend endpoints: `POST /lightrag/documents/upload`, `POST /lightrag/documents/paginated`, `GET /lightrag/documents/status_counts`, `GET /lightrag/documents/pipeline_status`, `GET /lightrag/documents/track_status/{track_id}`, `DELETE /lightrag/documents/delete_document`, `GET /lightrag/graph/label/popular`, `GET /lightrag/graph/label/search`, `GET /lightrag/graphs`.

- [ ] **Step 1: Add config**

Update `services/api_server/src/tutoring/core/config.py` with:

```python
lightrag_base_url: str = "http://localhost:19621"
lightrag_api_key: str | None = None
lightrag_timeout_seconds: float = 30.0
```

- [ ] **Step 2: Add schemas**

Create `services/api_server/src/tutoring/lightrag/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal[
    "pending", "parsing", "analyzing", "processing", "preprocessed", "processed", "failed"
]


class DocumentsRequest(BaseModel):
    status_filter: DocumentStatus | None = None
    status_filters: list[DocumentStatus] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_field: str = "updated_at"
    sort_direction: Literal["asc", "desc"] = "desc"


class DeleteDocumentRequest(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    delete_file: bool = True
    delete_llm_cache: bool = False
```

- [ ] **Step 3: Add service**

Create `services/api_server/src/tutoring/lightrag/service.py`:

```python
from collections.abc import Mapping
from typing import Any

import httpx

from tutoring.core.config import settings
from tutoring.core.errors import LightRAGError


def _url(path: str) -> str:
    return f"{settings.lightrag_base_url.rstrip('/')}/{path.lstrip('/')}"


def _headers() -> dict[str, str]:
    if not settings.lightrag_api_key:
        return {}
    return {"Authorization": f"Bearer {settings.lightrag_api_key}"}


async def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        async with httpx.AsyncClient(timeout=settings.lightrag_timeout_seconds) as client:
            response = await client.request(method, _url(path), headers=_headers(), **kwargs)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LightRAGError(
            f"LightRAG returned {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LightRAGError(f"LightRAG request failed: {exc}") from exc

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return {"message": response.text}


async def get_json(path: str, params: Mapping[str, Any] | None = None) -> Any:
    return await _request("GET", path, params=params)


async def post_json(path: str, payload: Mapping[str, Any] | None = None) -> Any:
    return await _request("POST", path, json=payload or {})


async def delete_json(path: str, payload: Mapping[str, Any] | None = None) -> Any:
    return await _request("DELETE", path, json=payload or {})


async def upload_file(path: str, filename: str, content: bytes, content_type: str) -> Any:
    files = {"file": (filename, content, content_type or "application/octet-stream")}
    return await _request("POST", path, files=files)
```

- [ ] **Step 4: Add router and app inclusion**

Create `services/api_server/src/tutoring/lightrag/router.py` with teacher-only route functions that call the service helpers. Use this delete behavior exactly:

```python
payload = body.model_dump()
payload["delete_file"] = True
return await lightrag_service.delete_json("/documents/delete_document", payload)
```

Create `services/api_server/src/tutoring/lightrag/__init__.py`:

```python
from tutoring.lightrag import router

__all__ = ["router"]
```

Modify `services/api_server/src/tutoring/app.py`:

```python
from tutoring.lightrag import router as lightrag_router

app.include_router(lightrag_router.router)
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/api_server"
uv run pytest tests/test_lightrag_proxy.py -q
uv run pytest -q
uv run ruff check src tests
```

Expected: all pass.

Commit:

```bash
git add services/api_server/src/tutoring/lightrag services/api_server/src/tutoring/core/config.py services/api_server/src/tutoring/app.py services/api_server/tests/test_lightrag_proxy.py
git commit -m "feat: add lightrag management proxy"
```

---

### Task 3: Frontend Client, Types, and Navigation

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api/lightrag.ts`
- Modify: `frontend/src/components/layout/ManagementLayout.tsx`

**Interfaces:**
- Consumes backend `/lightrag/*` routes from Task 2.
- Produces `lightragApi` methods for Task 4 and Task 5.

- [ ] **Step 1: Add dependencies**

Add these dependencies to `frontend/package.json`:

```json
"@react-sigma/core": "^5.0.6",
"@sigma/edge-curve": "^3.1.0",
"@sigma/node-border": "^3.0.0",
"graphology": "^0.26.0",
"graphology-layout-forceatlas2": "^0.10.1",
"minisearch": "^7.2.0",
"sigma": "^3.0.3",
"zustand": "^5.0.14"
```

Then run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npm install
```

- [ ] **Step 2: Add frontend types**

Append to `frontend/src/lib/types.ts`:

```ts
export type LightRAGDocumentStatus =
  | "pending"
  | "parsing"
  | "analyzing"
  | "processing"
  | "preprocessed"
  | "processed"
  | "failed";

export interface LightRAGDocument {
  id: string;
  content_summary?: string | null;
  content_length?: number | null;
  status: LightRAGDocumentStatus;
  created_at?: string | null;
  updated_at?: string | null;
  track_id?: string | null;
  chunks_count?: number | null;
  error_msg?: string | null;
  metadata?: Record<string, unknown>;
  file_path?: string | null;
}

export interface LightRAGDocumentsResponse {
  items: LightRAGDocument[];
  total: number;
  page: number;
  page_size: number;
}

export interface LightRAGPipelineStatus {
  busy: boolean;
  job_name?: string | null;
  docs?: number;
  cur_batch?: number;
  batchs?: number;
  request_pending?: boolean;
  latest_message?: string;
  history_messages?: string[];
}

export interface LightRAGGraphNode {
  id: string;
  labels?: string[];
  properties?: Record<string, unknown>;
}

export interface LightRAGGraphEdge {
  id?: string;
  source: string;
  target: string;
  type?: string;
  properties?: Record<string, unknown>;
}

export interface LightRAGGraphResponse {
  nodes: LightRAGGraphNode[];
  edges: LightRAGGraphEdge[];
}
```

- [ ] **Step 3: Add frontend API client**

Create `frontend/src/lib/api/lightrag.ts`:

```ts
import { api } from "./client";
import type {
  LightRAGDocumentsResponse,
  LightRAGDocumentStatus,
  LightRAGGraphResponse,
  LightRAGPipelineStatus,
} from "@/lib/types";

export const lightragApi = {
  uploadDocument: (formData: FormData) =>
    api.postForm<{ status: string; message: string; track_id: string }>(
      "/lightrag/documents/upload",
      formData,
    ),

  listDocuments: (params: {
    page: number;
    page_size: number;
    status_filter?: LightRAGDocumentStatus;
  }) => api.post<LightRAGDocumentsResponse>("/lightrag/documents/paginated", params),

  statusCounts: () =>
    api.get<{ status_counts: Record<string, number> }>(
      "/lightrag/documents/status_counts",
    ),

  pipelineStatus: () =>
    api.get<LightRAGPipelineStatus>("/lightrag/documents/pipeline_status"),

  trackStatus: (trackId: string) =>
    api.get<unknown>(`/lightrag/documents/track_status/${trackId}`),

  deleteDocument: (docId: string) =>
    api.delete<unknown>("/lightrag/documents/delete_document", {
      doc_ids: [docId],
      delete_file: true,
      delete_llm_cache: false,
    }),

  popularLabels: (limit = 300) =>
    api.get<string[] | { labels: string[] }>(
      `/lightrag/graph/label/popular?limit=${limit}`,
    ),

  searchLabels: (q: string, limit = 50) =>
    api.get<string[] | { labels: string[] }>(
      `/lightrag/graph/label/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  graph: (label: string, maxDepth = 3, maxNodes = 1000) =>
    api.get<LightRAGGraphResponse>(
      `/lightrag/graphs?label=${encodeURIComponent(label)}&max_depth=${maxDepth}&max_nodes=${maxNodes}`,
    ),
};
```

If `frontend/src/lib/api/client.ts` does not support DELETE request bodies, update `api.delete` to accept an optional `body?: unknown` and JSON-stringify it when provided.

- [ ] **Step 4: Add teacher nav item**

Modify `frontend/src/components/layout/ManagementLayout.tsx` to add a teacher nav item:

```ts
{
  href: "/teacher/manage/knowledge",
  label: "知识库",
  icon: Database,
}
```

Import `Database` from `lucide-react`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npx tsc --noEmit
```

Expected: TypeScript passes.

Commit:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/types.ts frontend/src/lib/api/lightrag.ts frontend/src/lib/api/client.ts frontend/src/components/layout/ManagementLayout.tsx
git commit -m "feat: add lightrag frontend client"
```

---

### Task 4: Knowledge Document Management UI

**Files:**
- Create: `frontend/src/app/teacher/manage/knowledge/page.tsx`
- Create: `frontend/src/components/knowledge/KnowledgeBasePage.tsx`
- Create: `frontend/src/components/knowledge/KnowledgeUpload.tsx`
- Create: `frontend/src/components/knowledge/KnowledgeDocumentTable.tsx`
- Create: `frontend/src/components/knowledge/KnowledgePipelineStatus.tsx`

**Interfaces:**
- Consumes `lightragApi` from Task 3.
- Produces teacher UI for upload, status, list, filter, pagination, and delete.

- [ ] **Step 1: Add route entry**

Create `frontend/src/app/teacher/manage/knowledge/page.tsx`:

```tsx
"use client";

import { KnowledgeBasePage } from "@/components/knowledge/KnowledgeBasePage";

export default function TeacherKnowledgePage() {
  return <KnowledgeBasePage />;
}
```

- [ ] **Step 2: Add upload component**

Create `KnowledgeUpload.tsx` with an `<Input type="file" />`, a submit button, `FormData` field name `file`, `lightragApi.uploadDocument(formData)`, success toast with returned `track_id`, and an `onUploaded` callback.

- [ ] **Step 3: Add status component**

Create `KnowledgePipelineStatus.tsx` that calls `lightragApi.pipelineStatus()` and `lightragApi.statusCounts()` on mount and on refresh. Display `busy`, `job_name`, `docs`, `cur_batch / batchs`, `latest_message`, and status count badges.

- [ ] **Step 4: Add document table**

Create `KnowledgeDocumentTable.tsx` using existing table style and `Pagination`. It must call `lightragApi.listDocuments({ page, page_size: 20, status_filter })`. Rows must show file path/name, status badge, chunks count, updated time, error message if failed, and a delete button. Delete must confirm and call `lightragApi.deleteDocument(doc.id)`.

- [ ] **Step 5: Add page shell**

Create `KnowledgeBasePage.tsx` with a header `知识库`, upload/status section, document table section, and a placeholder area for graph integration from Task 5. Use a `refreshKey` state that increments after upload/delete so status and table reload.

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npx tsc --noEmit
```

Expected: TypeScript passes.

Commit:

```bash
git add frontend/src/app/teacher/manage/knowledge frontend/src/components/knowledge
git commit -m "feat: add knowledge document management UI"
```

---

### Task 5: Knowledge Graph Viewer Integration

**Files:**
- Create: `frontend/src/components/knowledge/KnowledgeGraphPanel.tsx`
- Create: `frontend/src/components/knowledge/graph/GraphViewer.tsx`
- Create: `frontend/src/components/knowledge/graph/graphAdapter.ts`
- Create: `frontend/src/components/knowledge/graph/types.ts`
- Modify: `frontend/src/components/knowledge/KnowledgeBasePage.tsx`

**Interfaces:**
- Consumes `lightragApi.popularLabels`, `lightragApi.searchLabels`, and `lightragApi.graph`.
- Produces graph panel showing LightRAG nodes and relationships.

- [ ] **Step 1: Port only the required LightRAG WebUI graph pieces**

Use these source files as references, not blind copies:

```text
docs/_chat/LightRAG/lightrag_webui/src/features/GraphViewer.tsx
docs/_chat/LightRAG/lightrag_webui/src/components/graph/GraphControl.tsx
docs/_chat/LightRAG/lightrag_webui/src/hooks/useLightragGraph.tsx
docs/_chat/LightRAG/lightrag_webui/src/api/lightrag.ts
```

Keep the first Teaching Agent version smaller: one Sigma container, basic ForceAtlas/static layout, node labels, edge labels on selection, selected node/edge detail panel, zoom controls if easy.

- [ ] **Step 2: Add graph types and adapter**

Create `graph/types.ts`:

```ts
import type { LightRAGGraphEdge, LightRAGGraphNode } from "@/lib/types";

export interface KnowledgeGraphData {
  nodes: LightRAGGraphNode[];
  edges: LightRAGGraphEdge[];
}
```

Create `graph/graphAdapter.ts` that builds a `graphology` graph from `LightRAGGraphResponse`. Node label should prefer `node.properties?.entity_name`, then `node.id`. Edge label should prefer `edge.properties?.keywords`, then `edge.type`, then empty string. Edge weight should use numeric `edge.properties?.weight` or `1`.

- [ ] **Step 3: Add viewer component**

Create `GraphViewer.tsx` using `@react-sigma/core` and Graphology. Import Sigma CSS:

```ts
import "@react-sigma/core/lib/style.css";
```

The component props must be:

```ts
export function GraphViewer({ data }: { data: LightRAGGraphResponse })
```

Render empty state when `data.nodes.length === 0`.

- [ ] **Step 4: Add graph panel**

Create `KnowledgeGraphPanel.tsx` with popular labels, search input, max depth, max nodes, load button, loading state, and `GraphViewer`. Default label should be the first popular label when available.

- [ ] **Step 5: Wire page shell**

Modify `KnowledgeBasePage.tsx` to include `KnowledgeGraphPanel` below document management or in a two-tab layout using simple local state buttons `文件管理` and `知识图谱`.

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npx tsc --noEmit
```

Expected: TypeScript passes.

Commit:

```bash
git add frontend/src/components/knowledge frontend/package.json frontend/package-lock.json
git commit -m "feat: add lightrag knowledge graph viewer"
```

---

### Task 6: End-to-End Verification and Final Cleanup

**Files:**
- Modify only files required by failing verification.

**Interfaces:**
- Consumes Tasks 1-5.
- Produces verified, committed LightRAG integration.

- [ ] **Step 1: Run full backend verification**

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/api_server"
uv run pytest -q
uv run ruff check src tests
```

Expected: all tests and ruff pass.

- [ ] **Step 2: Run full frontend verification**

```bash
cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npx tsc --noEmit
```

Expected: TypeScript passes.

- [ ] **Step 3: Optional manual smoke test with running LightRAG**

Start or confirm LightRAG at `http://localhost:19621`, then visit `/teacher/manage/knowledge` as a teacher. Verify upload returns a track id, status refresh shows pipeline state, document list loads, delete prompts and succeeds, popular/search labels load, and graph renders for a selected label.

- [ ] **Step 4: Check git state**

```bash
git status --short
git diff --check
```

Expected: no whitespace errors; only intentional files are modified or untracked.

- [ ] **Step 5: Commit any cleanup**

If verification required changes:

```bash
git add <intentional-files>
git commit -m "fix: polish lightrag knowledge integration"
```

If no changes are needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: backend proxy, teacher-only auth, upload/list/status/delete, graph labels/graph rendering, and verification are covered.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: frontend `lightragApi` method names match component tasks; backend route names match contract tests.

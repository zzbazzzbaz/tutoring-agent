"""LightRAG HTTP 客户端。

在 lifespan 启动时启动一次，每请求复用。后端使用的所有端点都在此
封装，以便 agent 层和未来的代理端点共享一个连接池。
"""
import logging

import httpx

logger = logging.getLogger(__name__)


class LightRAGClient:
    """异步 LightRAG HTTP 客户端。"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """创建底层的 httpx.AsyncClient（带连接池）。"""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        logger.info("LightRAGClient started: %s", self.base_url)

    async def close(self) -> None:
        """关闭底层 httpx 客户端。"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """返回已启动的客户端，否则抛出。"""
        if self._client is None:
            raise RuntimeError("LightRAGClient not started; call start() first")
        return self._client

    # === 健康检查 ===

    async def health(self) -> dict:
        """GET /health."""
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    # === 文档管理（代理至前端）===

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        """POST /documents/upload（multipart）。"""
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self.client.post("/documents/upload", files=files)
        resp.raise_for_status()
        return resp.json()

    async def insert_text(self, body: dict) -> dict:
        """POST /documents/text."""
        resp = await self.client.post("/documents/text", json=body)
        resp.raise_for_status()
        return resp.json()

    async def insert_texts(self, body: dict) -> dict:
        """POST /documents/texts（批量）。"""
        resp = await self.client.post("/documents/texts", json=body)
        resp.raise_for_status()
        return resp.json()

    async def scan(self) -> dict:
        """POST /documents/scan（触发增量扫描）。"""
        resp = await self.client.post("/documents/scan")
        resp.raise_for_status()
        return resp.json()

    async def track_status(self, track_id: str) -> dict:
        """GET /documents/track_status/{track_id}."""
        resp = await self.client.get(f"/documents/track_status/{track_id}")
        resp.raise_for_status()
        return resp.json()

    async def pipeline_status(self) -> dict:
        """GET /documents/pipeline_status."""
        resp = await self.client.get("/documents/pipeline_status")
        resp.raise_for_status()
        return resp.json()

    async def status_counts(self) -> dict:
        """GET /documents/status_counts."""
        resp = await self.client.get("/documents/status_counts")
        resp.raise_for_status()
        return resp.json()

    async def list_documents(self, body: dict) -> dict:
        """POST /documents/paginated."""
        resp = await self.client.post("/documents/paginated", json=body)
        resp.raise_for_status()
        return resp.json()

    async def delete_documents(self, body: dict) -> dict:
        """DELETE /documents/delete_document."""
        resp = await self.client.request("DELETE", "/documents/delete_document", json=body)
        resp.raise_for_status()
        return resp.json()

    # === 查询（agent 工具内部使用；不暴露给前端）===

    async def query(
        self,
        query: str,
        mode: str = "mix",
        only_need_context: bool = False,
        include_references: bool = True,
        **kwargs,
    ) -> dict:
        """POST /query。

        将额外的 kwargs（top_k 等）透传给 LightRAG。
        """
        body = {
            "query": query,
            "mode": mode,
            "only_need_context": only_need_context,
            "include_references": include_references,
            **kwargs,
        }
        resp = await self.client.post("/query", json=body)
        resp.raise_for_status()
        return resp.json()

    # === 知识图谱（代理至前端）===

    async def get_graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000) -> dict:
        """GET /graphs."""
        resp = await self.client.get(
            "/graphs", params={"label": label, "max_depth": max_depth, "max_nodes": max_nodes}
        )
        resp.raise_for_status()
        return resp.json()

    async def list_labels(self) -> list[str]:
        """GET /graph/label/list."""
        resp = await self.client.get("/graph/label/list")
        resp.raise_for_status()
        return resp.json()

    async def popular_labels(self, limit: int = 300) -> list[str]:
        """GET /graph/label/popular."""
        resp = await self.client.get("/graph/label/popular", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def search_labels(self, query: str) -> list[str]:
        """GET /graph/label/search。

        注意：LightRAG API 使用 `q` 作为查询参数名，而非 `query`。
        """
        resp = await self.client.get("/graph/label/search", params={"q": query})
        resp.raise_for_status()
        return resp.json()

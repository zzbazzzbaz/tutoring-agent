"""LightRAG HTTP 客户端。

在 lifespan 启动时启动一次，每请求复用。后端使用的所有端点都在此
封装，以便 agent 层和代理端点共享一个连接池。

所有 httpx 错误统一包装为 LightRAGError，由全局异常处理器转 502。
"""
import logging

import httpx

from tutoring.core.errors import LightRAGError

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

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """统一请求入口：httpx 错误包装为 LightRAGError（由全局 handler 转 502）。"""
        try:
            resp = await self.client.request(method, url, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise LightRAGError(str(e)) from e
        return resp

    # === 健康检查 ===

    async def health(self) -> dict:
        """GET /health。"""
        resp = await self._request("GET", "/health")
        return resp.json()

    # === 文档管理（代理至前端）===

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> dict:
        """POST /documents/upload（multipart）。"""
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self._request("POST", "/documents/upload", files=files)
        return resp.json()

    async def insert_text(self, body: dict) -> dict:
        """POST /documents/text。"""
        resp = await self._request("POST", "/documents/text", json=body)
        return resp.json()

    async def scan(self) -> dict:
        """POST /documents/scan（触发增量扫描）。"""
        resp = await self._request("POST", "/documents/scan")
        return resp.json()

    async def pipeline_status(self) -> dict:
        """GET /documents/pipeline_status。"""
        resp = await self._request("GET", "/documents/pipeline_status")
        return resp.json()

    async def list_documents(self, body: dict) -> dict:
        """POST /documents/paginated。"""
        resp = await self._request("POST", "/documents/paginated", json=body)
        return resp.json()

    async def delete_documents(self, body: dict) -> dict:
        """DELETE /documents/delete_document。"""
        resp = await self._request("DELETE", "/documents/delete_document", json=body)
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
        resp = await self._request("POST", "/query", json=body)
        return resp.json()

    # === 知识图谱（代理至前端）===

    async def get_graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000) -> dict:
        """GET /graphs。"""
        resp = await self._request(
            "GET", "/graphs", params={"label": label, "max_depth": max_depth, "max_nodes": max_nodes}
        )
        return resp.json()

    async def list_labels(self) -> list[str]:
        """GET /graph/label/list。"""
        resp = await self._request("GET", "/graph/label/list")
        return resp.json()

    async def popular_labels(self, limit: int = 300) -> list[str]:
        """GET /graph/label/popular。"""
        resp = await self._request("GET", "/graph/label/popular", params={"limit": limit})
        return resp.json()

    async def search_labels(self, query: str) -> list[str]:
        """GET /graph/label/search。

        注意：LightRAG API 使用 `q` 作为查询参数名，而非 `query`。
        """
        resp = await self._request("GET", "/graph/label/search", params={"q": query})
        return resp.json()

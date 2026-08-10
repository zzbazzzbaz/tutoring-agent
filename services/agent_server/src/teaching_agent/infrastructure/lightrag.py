import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from teaching_agent.config import get_settings

logger = logging.getLogger(__name__)

_QUERY_OPTIONS = {
    "mode": "hybrid",
    "only_need_context": True,
    "top_k": 15,
    "chunk_top_k": 10,
    "max_entity_tokens": 3000,
    "max_relation_tokens": 3000,
    "max_total_tokens": 8000,
    "enable_rerank": False,
}
_MAX_ATTEMPTS = 2


class LightRAGError(Exception):
    """LightRAG returned no usable answer or could not be reached."""


class LightRAGClient:
    def __init__(self, client: httpx.AsyncClient, query_url: str) -> None:
        self._client = client
        self._query_url = query_url

    async def search(self, query: str) -> str:
        payload = {"query": query, **_QUERY_OPTIONS}
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._client.post(self._query_url, json=payload)
                response.raise_for_status()
                result = self._response_text(response.json())
                if result:
                    return result
                raise LightRAGError("LightRAG returned an empty response")
            except (httpx.HTTPError, ValueError, LightRAGError) as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise LightRAGError("Knowledge search is unavailable") from exc
                logger.warning("LightRAG request failed; retrying", exc_info=exc)
                await asyncio.sleep(0.2 * attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def _response_text(payload: Any) -> str:
        result = payload.get("response", "") if isinstance(payload, dict) else ""
        return result.strip() if isinstance(result, str) else ""


@asynccontextmanager
async def lightrag_client() -> AsyncIterator[LightRAGClient]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        yield LightRAGClient(client, settings.lightrag_query_url)

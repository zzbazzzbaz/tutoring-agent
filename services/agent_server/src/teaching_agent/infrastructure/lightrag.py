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

    async def search(self, query: str) -> dict:
        payload = {"query": query, **_QUERY_OPTIONS}
        data_url = f"{self._query_url}/data"
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                text_resp, data_resp = await asyncio.gather(
                    self._client.post(self._query_url, json=payload),
                    self._client.post(data_url, json=payload),
                )
                text_resp.raise_for_status()
                data_resp.raise_for_status()
                result = self._combine(text_resp.json(), data_resp.json(), query)
                if result["response"] or result["entities"] or result["chunks"]:
                    return result
                raise LightRAGError("LightRAG returned an empty response")
            except (httpx.HTTPError, ValueError, LightRAGError) as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise LightRAGError("Knowledge search is unavailable") from exc
                logger.warning("LightRAG request failed; retrying", exc_info=exc)
                await asyncio.sleep(0.2 * attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def _as_list(value: Any) -> list[dict]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @classmethod
    def _combine(cls, text_payload: Any, data_payload: Any, query: str) -> dict:
        result = {"query": query, "response": "", "chunks": [], "entities": [], "relations": []}
        if isinstance(text_payload, dict):
            response = text_payload.get("response", "")
            result["response"] = response.strip() if isinstance(response, str) else ""
        data = data_payload.get("data") if isinstance(data_payload, dict) else None
        if isinstance(data, dict):
            result["chunks"] = cls._as_list(data.get("chunks"))
            result["entities"] = cls._as_list(data.get("entities"))
            result["relations"] = cls._as_list(data.get("relationships"))
        return result


@asynccontextmanager
async def lightrag_client() -> AsyncIterator[LightRAGClient]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        yield LightRAGClient(client, settings.lightrag_query_url)

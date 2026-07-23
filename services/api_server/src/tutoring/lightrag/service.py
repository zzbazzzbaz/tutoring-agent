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

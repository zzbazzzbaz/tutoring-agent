from typing import Literal
from uuid import UUID

import httpx

from teaching_agent.auth.schemas import AuthorizedPrincipal
from teaching_agent.config import get_settings


class APIServerAuthorizationError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def authorize_with_api_server(
    authorization: str,
    *,
    session_id: UUID | None,
    access: Literal["identity", "read", "run"],
    touch: bool = False,
) -> AuthorizedPrincipal:
    settings = get_settings()
    headers = {
        "Authorization": authorization,
        "X-Agent-Server-Secret": settings.agent_server_secret.get_secret_value(),
    }
    payload = {
        "session_id": str(session_id) if session_id else None,
        "access": access,
        "touch": touch,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.backend_internal_url.rstrip('/')}/auth/internal/agent/authorize",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise APIServerAuthorizationError(503, "API Server authorization is unavailable") from exc
    if response.status_code >= 400:
        raise APIServerAuthorizationError(response.status_code, "API Server rejected the request")
    try:
        return AuthorizedPrincipal.model_validate(response.json())
    except ValueError as exc:
        raise APIServerAuthorizationError(
            502, "API Server returned an invalid authorization response"
        ) from exc

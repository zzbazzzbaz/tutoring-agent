from uuid import UUID

import httpx

from teaching_agent.config import get_settings
from teaching_agent.schemas import AuthorizedPrincipal


class BackendAuthorizationError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def authorize_with_backend(
    authorization: str,
    *,
    session_id: UUID | None,
    access: str,
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
                f"{settings.backend_internal_url.rstrip('/')}/internal/agent/authorize",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise BackendAuthorizationError(503, "Backend authorization is unavailable") from exc
    if response.status_code >= 400:
        raise BackendAuthorizationError(response.status_code, "Backend rejected the request")
    try:
        return AuthorizedPrincipal.model_validate(response.json())
    except ValueError as exc:
        raise BackendAuthorizationError(
            502, "Backend returned an invalid authorization response"
        ) from exc

import re
from typing import Any
from uuid import UUID

from langgraph_sdk import Auth

from teaching_agent.infrastructure.api_server_client import (
    APIServerAuthorizationError,
    authorize_with_api_server,
)

auth = Auth()
_THREAD_PATH = re.compile(r"^/threads/([^/]+)(?:/|$)")
_THREAD_COLLECTION_ACTIONS = {"count", "prune", "search"}


def _thread_id(path: str, path_params: dict[str, str] | None) -> UUID | None:
    match = _THREAD_PATH.match(path)
    raw = (path_params or {}).get("thread_id") or (match.group(1) if match else None)
    if not raw or raw in _THREAD_COLLECTION_ACTIONS:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise Auth.exceptions.HTTPException(status_code=422, detail="Invalid thread ID") from exc


@auth.authenticate
async def authenticate(
    path: str,
    method: str,
    path_params: dict[str, str] | None,
    authorization: str | None,
) -> dict:
    if path == "/ok":
        return {"identity": "health-check", "role": "teacher", "name": "health-check"}
    if not authorization or not authorization.startswith("Bearer "):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Missing bearer token")

    session_id = _thread_id(path, path_params)
    is_run = session_id is not None and method == "POST" and "/runs" in path
    access = "run" if is_run else "read" if session_id is not None else "identity"
    try:
        principal = await authorize_with_api_server(
            authorization,
            session_id=session_id,
            access=access,
            touch=is_run,
        )
    except APIServerAuthorizationError as exc:
        status = exc.status_code if exc.status_code in {401, 403, 404, 422, 503} else 502
        raise Auth.exceptions.HTTPException(status_code=status, detail=exc.detail) from exc

    permissions = ["threads:read"]
    if principal.session_access == "run":
        permissions.append("threads:run")
    return principal.model_dump(mode="json", exclude_none=True) | {"permissions": permissions}


@auth.on
async def deny_unhandled(ctx: Auth.types.AuthContext, value: Any) -> bool:
    del ctx, value
    return False


@auth.on.assistants.read
async def read_system_assistant(ctx: Auth.types.AuthContext, value: dict) -> None:
    del ctx, value
    return None


@auth.on.threads.search
async def search_threads(ctx: Auth.types.AuthContext, value: dict):
    del value
    if ctx.user.role == "teacher":
        return None
    return {"owner": ctx.user.identity}


@auth.on.threads.create
async def create_thread(ctx: Auth.types.AuthContext, value: dict):
    value.setdefault("metadata", {})["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}


@auth.on.threads.read
async def read_thread(ctx: Auth.types.AuthContext, value: dict):
    session_id = getattr(ctx.user, "session_id", None)
    if not session_id or str(value.get("thread_id")) != str(session_id):
        return False
    if ctx.user.role == "teacher":
        return None
    return {"owner": ctx.user.identity}


@auth.on.threads.create_run
async def create_run(ctx: Auth.types.AuthContext, value: dict):
    session_id = getattr(ctx.user, "session_id", None)
    if (
        getattr(ctx.user, "session_access", None) != "run"
        or not session_id
        or str(value.get("thread_id")) != str(session_id)
    ):
        return False
    value.setdefault("metadata", {})["owner"] = ctx.user.identity
    value.setdefault("kwargs", {}).pop("context", None)
    return {"owner": ctx.user.identity}

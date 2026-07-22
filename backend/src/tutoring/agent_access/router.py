import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.agent_access.schemas import (
    AgentAuthorizeRequest,
    AgentAuthorizeResponse,
    AgentContextV1,
)
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.sessions import service as session_service

router = APIRouter(prefix="/internal/agent", tags=["internal-agent"])


def require_agent_server(
    x_agent_server_secret: str | None = Header(None),
) -> None:
    if not x_agent_server_secret or not hmac.compare_digest(
        x_agent_server_secret, settings.agent_server_secret
    ):
        raise AppError(403, "INVALID_AGENT_SERVER", "Invalid Agent Server credential")


@router.post(
    "/authorize",
    response_model=AgentAuthorizeResponse,
    dependencies=[Depends(require_agent_server)],
)
async def authorize_agent_request(
    body: AgentAuthorizeRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> AgentAuthorizeResponse:
    if body.access == "identity":
        return AgentAuthorizeResponse(
            identity=str(user.id),
            role=user.role,
            name=user.name,
            session_access="identity",
        )

    if body.access == "run":
        session = await session_service.get_writable_session(db_session, body.session_id, user)
        if body.touch:
            await session_service.touch_session(db_session, body.session_id)
    else:
        session = await session_service.get_readable_session(db_session, body.session_id, user)

    context = AgentContextV1.model_validate(
        await session_service.build_agent_context(db_session, session)
    )
    return AgentAuthorizeResponse(
        identity=str(user.id),
        role=user.role,
        name=user.name,
        session_id=session.id,
        session_access=body.access,
        agent_context=context,
    )

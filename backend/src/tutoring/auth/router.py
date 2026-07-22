import hmac

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth import service as auth_service
from tutoring.auth.schemas import (
    AgentAuthorizeRequest,
    AgentAuthorizeResponse,
    AgentContextV1,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    UserPublic,
)
from tutoring.core.config import settings
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.sessions import service as session_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db_session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    token = await auth_service.login(db_session, body.username, body.password)
    user = await auth_service.verify_token(db_session, token)
    return LoginResponse(token=token, user=UserPublic.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db_session: AsyncSession = Depends(get_db),
) -> None:
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token:
        await auth_service.logout(db_session, token)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user.id, username=user.username, role=user.role, name=user.name
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    db_user = await repos.get_user_by_id(db_session, user.id)
    await auth_service.change_password(db_session, db_user, body.old_password, body.new_password)


def require_agent_server(
    x_agent_server_secret: str | None = Header(None),
) -> None:
    if not x_agent_server_secret or not hmac.compare_digest(
        x_agent_server_secret, settings.agent_server_secret
    ):
        raise AppError(403, "INVALID_AGENT_SERVER", "Invalid Agent Server credential")


@router.post(
    "/internal/agent/authorize",
    response_model=AgentAuthorizeResponse,
    dependencies=[Depends(require_agent_server)],
    tags=["internal-agent"],
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

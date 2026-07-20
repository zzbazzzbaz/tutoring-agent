"""认证路由：login / logout / me。"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth import service as auth_service
from tutoring.auth.schemas import LoginRequest, LoginResponse, MeResponse, UserPublic
from tutoring.core.deps import CurrentUser, get_current_user, get_db

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

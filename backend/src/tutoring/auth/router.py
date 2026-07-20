"""认证路由：login / logout / me。"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth import service as auth_service
from tutoring.auth.schemas import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse, UserPublic
from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.db import repos

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

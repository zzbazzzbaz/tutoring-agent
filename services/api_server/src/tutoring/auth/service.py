import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Session, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


async def login(db: AsyncSession, username: str, password: str) -> str:
    user = await repos.get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    token = await repos.create_token(db, user.id)
    return token.token


async def logout(db: AsyncSession, token: str) -> None:
    await repos.delete_token(db, token)


async def verify_token(db: AsyncSession, token: str) -> User:
    auth_token = await repos.get_token_with_user(db, token)
    if not auth_token or not auth_token.user:
        raise AppError(401, "INVALID_TOKEN", "无效或已过期的 token")
    return auth_token.user


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> None:
    if not verify_password(old_password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "旧密码错误")
    await repos.update_password(db, user.id, hash_password(new_password))


async def build_agent_context(db: AsyncSession, sess: Session) -> dict:
    """构造传给 Server 的 context dict（与 AgentContext 字段一致，Server 侧再强转）。"""
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return {
            "mode": "project",
            "project_name": proj.name if proj else "",
            "project_background_md": proj.background_md if proj else "",
        }
    return {"mode": "free"}

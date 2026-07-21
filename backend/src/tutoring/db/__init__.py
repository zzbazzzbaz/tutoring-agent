"""Database layer: models and repository functions."""
from tutoring.db.models import AuthToken, Project, Session, User
from tutoring.db.repos import (
    # User
    get_user_by_username,
    get_user_by_id,
    create_user,
    list_users_by_role,
    delete_user,
    update_password,
    # AuthToken
    create_token,
    get_token_with_user,
    delete_token,
    # Session
    create_session,
    get_session,
    list_sessions,
    touch_session,
    delete_session,
    # Project
    create_project,
    get_project,
    list_projects,
    update_project,
    delete_project,
)

__all__ = [
    "AuthToken",
    "Project",
    "Session",
    "User",
    "get_user_by_username",
    "get_user_by_id",
    "create_user",
    "list_users_by_role",
    "delete_user",
    "update_password",
    "create_token",
    "get_token_with_user",
    "delete_token",
    "create_session",
    "get_session",
    "list_sessions",
    "touch_session",
    "delete_session",
    "create_project",
    "get_project",
    "list_projects",
    "update_project",
    "delete_project",
]

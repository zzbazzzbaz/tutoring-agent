"""Database layer: models and repository functions.

Re-export repository functions for ergonomic access via `from
tutoring import db; await db.create_project(...)`.
Engine/session factory located at core.database.
"""
from tutoring.db.models import AuthToken, Project, Session, ChatEvent, User
from tutoring.db.repos import (
    ToolEventData,
    QuizEventData,
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
    # ChatEvent
    save_event,
    list_events,
    update_quiz_status,
    has_pending_quiz,
    get_last_user_event,
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
    "ChatEvent",
    "User",
    "ToolEventData",
    "QuizEventData",
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
    "save_event",
    "list_events",
    "update_quiz_status",
    "has_pending_quiz",
    "get_last_user_event",
    "create_project",
    "get_project",
    "list_projects",
    "update_project",
    "delete_project",
]

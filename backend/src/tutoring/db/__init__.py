"""Database layer: models and repository functions.

Re-export repository functions for ergonomic access via `from
tutoring import db; await db.create_project(...)`.
Engine/session factory 位于 core.database。
"""
from tutoring.db.models import Project, Session, Message, Question
from tutoring.db.repos import (
    # Session
    create_session,
    get_session,
    list_sessions,
    touch_session,
    end_session,
    # Message
    save_message,
    list_messages,
    # Question
    upsert_pending_question,
    get_pending_question,
    update_question,
    list_questions,
    # Project
    create_project,
    get_project,
    list_projects,
    update_project,
    delete_project,
)

__all__ = [
    # Models
    "Project",
    "Session",
    "Message",
    "Question",
    # Session repos
    "create_session",
    "get_session",
    "list_sessions",
    "touch_session",
    "end_session",
    # Message repos
    "save_message",
    "list_messages",
    # Question repos
    "upsert_pending_question",
    "get_pending_question",
    "update_question",
    "list_questions",
    # Project repos
    "create_project",
    "get_project",
    "list_projects",
    "update_project",
    "delete_project",
]

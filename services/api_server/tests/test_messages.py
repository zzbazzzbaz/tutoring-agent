from types import SimpleNamespace
from uuid import uuid4

import pytest

from tutoring.core.errors import AppError
from tutoring.messages import service as message_service
from tutoring.messages.schemas import AgentMessageItem


class _ExistingSessionDB:
    """mock db：session 存在且未删除。"""

    def __init__(self):
        self.session = SimpleNamespace(id=uuid4(), deleted_at=None)

    async def get(self, _model, session_id):
        return self.session if self.session.id == session_id else None


class _MissingSessionDB:
    async def get(self, _model, _session_id):
        return None


@pytest.mark.asyncio
async def test_persist_agent_messages_writes_items(monkeypatch):
    captured = {}

    async def fake_create_messages(_db, *, session_id, items):
        captured["session_id"] = session_id
        captured["items"] = items
        return len(items)

    monkeypatch.setattr("tutoring.db.repos.create_messages", fake_create_messages)

    db = _ExistingSessionDB()
    written = await message_service.persist_agent_messages(
        db,
        session_id=db.session.id,
        items=[
            AgentMessageItem(
                role="student",
                content="学生提问",
                knowledge_hit=True,
                knowledge_doc_ids=["心理学/情绪.md", "心理学/记忆.md"],
            ),
            AgentMessageItem(role="assistant", content="AI回复", knowledge_hit=False),
        ],
    )

    assert written == 2
    assert captured["session_id"] == db.session.id
    assert captured["items"][0]["knowledge_hit"] is True
    assert captured["items"][0]["knowledge_doc_ids"] == ["心理学/情绪.md", "心理学/记忆.md"]
    assert captured["items"][1]["knowledge_hit"] is False
    assert captured["items"][1]["knowledge_doc_ids"] == []


@pytest.mark.asyncio
async def test_persist_agent_messages_empty_items_returns_zero(monkeypatch):
    called = []

    async def fake_create_messages(*args, **kwargs):
        called.append(kwargs)
        return 0

    monkeypatch.setattr("tutoring.db.repos.create_messages", fake_create_messages)

    db = _ExistingSessionDB()
    written = await message_service.persist_agent_messages(
        db, session_id=db.session.id, items=[]
    )

    assert written == 0
    assert called == []


@pytest.mark.asyncio
async def test_persist_agent_messages_rejects_missing_session():
    with pytest.raises(AppError) as exc_info:
        await message_service.persist_agent_messages(
            _MissingSessionDB(), session_id=uuid4(), items=[]
        )
    assert exc_info.value.status_code == 404

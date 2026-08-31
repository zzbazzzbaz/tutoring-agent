# 消息记录--路由（内部端点）
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.auth.router import require_agent_server
from tutoring.core.deps import get_db
from tutoring.messages import service as message_service
from tutoring.messages.schemas import (
    AgentMessageBulkWriteRequest,
    AgentMessageBulkWriteResponse,
)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post(
    "/internal/agent",
    response_model=AgentMessageBulkWriteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_agent_server)],
    tags=["internal-agent"],
)
async def write_agent_messages(
    body: AgentMessageBulkWriteRequest,
    db_session: AsyncSession = Depends(get_db),
) -> AgentMessageBulkWriteResponse:
    """Agent Server 每回合结束后写入本轮学生提问 + AI 回复（内部端点，需 X-Agent-Server-Secret）。"""
    written = await message_service.persist_agent_messages(
        db_session,
        session_id=body.session_id,
        items=body.messages,
    )
    return AgentMessageBulkWriteResponse(written=written)

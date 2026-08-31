# 消息落库中间件：每回合 agent 执行结束后写入 API Server
import logging
from uuid import UUID

import httpx
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from teaching_agent.config import get_settings

logger = logging.getLogger(__name__)

# 知识检索工具名（tools/knowledge.py 中 @tool 装饰的函数名）
_KNOWLEDGE_TOOL_NAME = "search_knowledge"


class MessagePersistenceMiddleware(AgentMiddleware):
    """每回合 agent 执行结束后，把本轮学生提问 + AI 回复写入 API Server。

    - 挂载点：after_agent（agent 完成后运行），对应图中的 `message_persistence.after_agent` 节点
    - 会话标识：`runtime.execution_info.thread_id`（= API Server 的 Session.id）
    - 知识命中：本轮是否调用过 `search_knowledge` 工具（ToolMessage.name / AIMessage.tool_calls）
    - 失败不影响聊天：落库全程 try/except，只记日志
    """

    async def aafter_agent(self, state: dict, runtime: Runtime) -> dict | None:
        try:
            execution_info = getattr(runtime, "execution_info", None)
            thread_id = getattr(execution_info, "thread_id", None) if execution_info else None
            if not thread_id:
                logger.debug("No thread_id in execution_info, skip message persistence")
                return None

            messages = list((state or {}).get("messages") or [])
            student_content, ai_content = _extract_turn(messages)
            if student_content is None and ai_content is None:
                logger.debug("No new turn extracted, skip message persistence")
                return None

            knowledge_hit = _has_knowledge_hit(messages)
            await _persist(
                session_id=UUID(str(thread_id)),
                student_content=student_content,
                ai_content=ai_content,
                knowledge_hit=knowledge_hit,
            )
        except Exception:
            # 落库失败不影响聊天主流程
            logger.exception("Failed to persist messages to API Server")
        return None


def _extract_turn(messages: list) -> tuple[str | None, str | None]:
    """从最终 state 提取本轮最后一条学生提问 + AI 最终回复。

    返回 (student_content, ai_content)，缺失部分为 None。
    """
    student_content: str | None = None
    ai_content: str | None = None
    for msg in messages:
        if isinstance(msg, HumanMessage) and msg.content:
            student_content = _content_text(msg)
        elif isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            # 终态 AI 回复：有正文且非工具调用消息
            ai_content = _content_text(msg)
    return student_content, ai_content


def _has_knowledge_hit(messages: list) -> bool:
    """本轮（最后一条学生提问之后）是否调用过知识检索工具。
        为知识命中率提供数据支撑(本轮学生提问是否命中知识库)
    """
    last_human_idx = -1
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_idx = i
    if last_human_idx < 0:
        return False
    for msg in messages[last_human_idx:]:
        if getattr(msg, "name", None) == _KNOWLEDGE_TOOL_NAME:
            return True
        tool_calls = getattr(msg, "tool_calls", None) or []
        if any(tc.get("name") == _KNOWLEDGE_TOOL_NAME for tc in tool_calls):
            return True
    return False


def _content_text(msg) -> str:
    """提取消息正文文本（兼容 str 与多模态 list）。"""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


async def _persist(
    *,
    session_id: UUID,
    student_content: str | None,
    ai_content: str | None,
    knowledge_hit: bool,
) -> None:
    """调用 API Server 内部端点写入消息。"""
    settings = get_settings()
    payload = {"session_id": str(session_id), "messages": []}
    if student_content is not None:
        payload["messages"].append(
            {"role": "student", "content": student_content, "knowledge_hit": knowledge_hit}
        )
    if ai_content is not None:
        payload["messages"].append(
            {"role": "assistant", "content": ai_content, "knowledge_hit": False}
        )
    if not payload["messages"]:
        return

    headers = {"X-Agent-Server-Secret": settings.agent_server_secret.get_secret_value()}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.backend_internal_url.rstrip('/')}/messages/internal/agent",
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        logger.warning(
            "Persist messages to API Server failed: %s %s",
            response.status_code,
            response.text[:500],
        )

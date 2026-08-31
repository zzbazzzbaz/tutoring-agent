# Agent 中间件装配：工具重试 + 上下文压缩 + 消息落库
import operator
from typing import Annotated, Any

from langchain.agents.middleware import (
    AgentMiddleware,
    SummarizationMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.middleware.types import AgentState

from teaching_agent.auth.schemas import AgentContextV1
from teaching_agent.config import get_settings
from teaching_agent.infrastructure.llm import get_llm
from teaching_agent.infrastructure.message_persistence import MessagePersistenceMiddleware


class ProjectProgressState(AgentState):
    """在 agent 状态上增加 progress 键，供前端实时展示学习主线进度。"""

    progress: Annotated[dict[str, Any], operator.or_]


class ProjectProgressMiddleware(AgentMiddleware):
    """声明 progress 状态字段；进度内容由 report_stage_progress 工具写入。"""

    state_schema = ProjectProgressState


def build_middleware(context: AgentContextV1 | None = None) -> list:
    """按顺序装配全部中间件：

    1. ToolRetryMiddleware：单个工具调用失败时指数退避重试，超过上限后把错误注入
       给 agent 继续（而不是直接中断整轮对话）
    2. SummarizationMiddleware：消息历史 token 超阈值时，用 LLM 摘要压缩旧消息，
       保留最近 N 条，避免上下文无限膨胀
    3. MessagePersistenceMiddleware：每轮对话结束后落库（原有逻辑）
    4. ProjectProgressMiddleware（仅项目模式且有学习主线）：声明 progress 状态，
       支撑学习主线进度实时展示
    """
    settings = get_settings()
    middleware: list = [
        ToolRetryMiddleware(
            max_retries=settings.agent_tool_max_retries,
            retry_on=(Exception,),
            on_failure="continue",
        ),
        SummarizationMiddleware(
            model=get_llm(),
            trigger=("tokens", settings.agent_context_trigger_tokens),
            keep=("messages", settings.agent_context_keep_messages),
        ),
        MessagePersistenceMiddleware(),
    ]
    if context is not None and context.mode == "project" and context.project_mainline:
        middleware.append(ProjectProgressMiddleware())
    return middleware
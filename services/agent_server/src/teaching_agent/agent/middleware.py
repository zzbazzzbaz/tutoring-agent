# Agent 中间件装配：工具重试 + 上下文压缩 + 消息落库
from langchain.agents.middleware import SummarizationMiddleware, ToolRetryMiddleware

from teaching_agent.config import get_settings
from teaching_agent.infrastructure.llm import get_llm
from teaching_agent.infrastructure.message_persistence import MessagePersistenceMiddleware


def build_middleware() -> list:
    """按顺序装配全部中间件：

    1. ToolRetryMiddleware：单个工具调用失败时指数退避重试，超过上限后把错误注入
       给 agent 继续（而不是直接中断整轮对话）
    2. SummarizationMiddleware：消息历史 token 超阈值时，用 LLM 摘要压缩旧消息，
       保留最近 N 条，避免上下文无限膨胀
    3. MessagePersistenceMiddleware：每轮对话结束后落库（原有逻辑）
    """
    settings = get_settings()
    return [
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
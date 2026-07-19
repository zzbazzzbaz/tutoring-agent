"""ChatOpenAI 工厂，配置为 DashScope（OpenAI 兼容端点）。

LangChain 1.x：使用 langchain_openai.ChatOpenAI，不使用已废弃的 langchain.chat_models。
"""
from langchain_openai import ChatOpenAI

from teaching_agent_api.config import settings


def get_llm() -> ChatOpenAI:
    """返回配置好的 ChatOpenAI 实例（DashScope qwen3.6-flash）。

    Notes:
    - enable_thinking=False：关闭 DashScope 的思考输出，避免干扰
    - temperature=0.7：教学场景适度发散
    """
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )

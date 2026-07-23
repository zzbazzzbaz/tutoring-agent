from langchain_openai import ChatOpenAI

from teaching_agent.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=settings.dashscope_base_url,
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )

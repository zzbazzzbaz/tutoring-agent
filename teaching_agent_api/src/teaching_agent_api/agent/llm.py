from langchain_openai import ChatOpenAI

from teaching_agent_api.config import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )

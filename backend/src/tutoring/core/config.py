"""应用配置，由 .env 通过 pydantic-settings 驱动。"""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str

    # LLM（DashScope，OpenAI 兼容）
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.6-flash"

    # 课程
    course_name: str = "计算机网络"
    course_intro: str = ""

    # 服务器
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"

    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "teaching-agent"


settings = Settings()


def setup_langsmith() -> None:
    """把 LangSmith 配置推到 os.environ，让 langchain 自动埋点生效。"""
    if not settings.langsmith_tracing:
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

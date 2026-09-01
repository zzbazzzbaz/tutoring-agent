from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dashscope_api_key: SecretStr
    dashscope_base_url: str
    llm_model: str
    backend_internal_url: str
    agent_server_secret: SecretStr
    lightrag_query_url: str

    # === Agent 中间件 ===
    agent_tool_max_retries: int
    agent_context_trigger_tokens: int
    agent_context_keep_messages: int


@lru_cache
def get_settings() -> Settings:
    return Settings()

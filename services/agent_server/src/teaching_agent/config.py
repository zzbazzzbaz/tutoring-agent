from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_SHARED_ENV_FILE = Path(__file__).resolve().parents[2].parent / "api_server" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_SHARED_ENV_FILE, extra="ignore")

    dashscope_api_key: SecretStr
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.6-flash"
    backend_internal_url: str = "http://127.0.0.1:8000"
    agent_server_secret: SecretStr
    lightrag_query_url: str = "http://127.0.0.1:19621/query"


@lru_cache
def get_settings() -> Settings:
    return Settings()

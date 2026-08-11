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

    # === Prompts ===
    course_name: str = "普通心理学"
    prompt_core_principles: str = ""
    prompt_free_template: str = ""
    prompt_project_template: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

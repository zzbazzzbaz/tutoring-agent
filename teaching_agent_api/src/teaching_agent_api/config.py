"""应用配置，由 .env 通过 pydantic-settings 驱动。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str

    # LightRAG
    lightrag_base_url: str
    lightrag_api_key: str

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


settings = Settings()

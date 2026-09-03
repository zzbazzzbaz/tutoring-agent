from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    agent_server_secret: str
    upload_dir: str = "uploads"
    lightrag_base_url: str = "http://localhost:19621"
    lightrag_api_key: str | None = None
    lightrag_timeout_seconds: float = 30.0

    # LLM 研究摘要（DashScope 通义千问，OpenAI 兼容接口）
    # 未配置/占位符时摘要服务优雅降级，不影响 API 启动
    dashscope_api_key: SecretStr | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.7-flash"


settings = Settings()

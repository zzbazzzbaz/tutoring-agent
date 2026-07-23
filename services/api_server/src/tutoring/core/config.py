from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    agent_server_secret: str
    upload_dir: str = "uploads"
    lightrag_base_url: str = "http://localhost:19621"
    lightrag_api_key: str | None = None
    lightrag_timeout_seconds: float = 30.0


settings = Settings()

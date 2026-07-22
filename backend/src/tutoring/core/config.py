from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str

    # 课程
    course_name: str = "计算机网络"
    cors_origins: str = "*"

    agent_server_secret: str


settings = Settings()

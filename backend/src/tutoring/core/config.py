from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str

    # 课程
    course_name: str = "计算机网络"
    course_intro: str = ""

    # 服务器
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"

    # LangGraph Server
    langgraph_server_url: str = "http://localhost:2024"
    agent_server_secret: str


settings = Settings()

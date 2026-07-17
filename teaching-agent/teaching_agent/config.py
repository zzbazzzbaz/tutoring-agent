from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DashScope
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL: str = "qwen3.6-flash"
    EMBEDDING_MODEL: str = "text-embedding-v4"

    # 数据库
    DATABASE_URL: str = ""

    # 课程配置
    COURSE_NAME: str = ""
    COURSE_INTRO: str = ""
    TEACHING_STYLE: str = ""

    # 检索参数
    DISTANCE_THRESHOLD: float = 0.5
    TOP_K: int = 5
    RECURSION_LIMIT: int = 15

    model_config = {"env_file": ".env"}


settings = Settings()

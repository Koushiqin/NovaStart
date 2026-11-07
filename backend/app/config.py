from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，键名与 .env.example 一一对应。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart"
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    clock_mode: str = "normal"
    demo_time_offset_seconds: int = 0
    # 会话有效性阈值（秒）：默认 5 分钟 ~ 180 分钟；演示加速只调这两个值
    session_min_seconds: int = 300
    session_max_seconds: int = 10800


settings = Settings()

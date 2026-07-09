from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HelloAgents Trip Planner"
    app_version: str = "1.0.1"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kxh-trip-planner.netlify.app",
    ]
    use_mock_llm: bool = True
    use_mock_tools: bool = True
    use_mock_images: bool = True
    tavily_api_key: str = ""
    amap_api_key: str = ""
    unsplash_access_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.moonshot.cn/v1"
    model_name: str = "kimi-k2.6"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

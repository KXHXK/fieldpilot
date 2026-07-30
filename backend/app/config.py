from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FieldPilot API"
    app_version: str = "0.1.0"
    use_mock_tools: bool = True
    use_mock_llm: bool = True
    amap_api_key: str = ""
    tavily_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.moonshot.cn/v1"
    model_name: str = "kimi-k2.6"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

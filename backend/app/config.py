from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Convert provider-style PostgreSQL URLs to SQLAlchemy asyncpg URLs."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        return value

    query: list[tuple[str, str]] = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "sslmode":
            query.append(("ssl", item))
        elif key != "channel_binding":
            query.append((key, item))
    return urlunsplit(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


class Settings(BaseSettings):
    app_name: str = "FieldPilot API"
    app_version: str = "0.6.0"
    use_mock_llm: bool = True
    amap_api_key: str = ""
    amap_base_url: str = "https://restapi.amap.com"
    local_route_provider: Literal["fixture", "amap"] = "fixture"
    manual_candidate_file: str = ""
    provider_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    provider_max_retries: int = Field(default=1, ge=0, le=3)
    provider_max_concurrency: int = Field(default=4, ge=1, le=10)
    provider_max_live_calls: int = Field(default=32, ge=1, le=100)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.moonshot.cn/v1"
    model_name: str = "kimi-k2.6"
    llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    llm_total_tokens_limit: int = Field(default=6000, ge=500, le=50_000)
    cors_origins: str = "http://localhost:5173"
    database_url: str = "sqlite+aiosqlite:///./fieldpilot.db"
    database_auto_create: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

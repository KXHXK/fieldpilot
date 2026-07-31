from app.config import Settings, normalize_database_url


def test_neon_style_database_url_is_normalized_for_asyncpg() -> None:
    raw = (
        "postgresql://fieldpilot:secret@example.neon.tech/fieldpilot"
        "?sslmode=require&channel_binding=require"
    )

    assert normalize_database_url(raw) == (
        "postgresql+asyncpg://fieldpilot:secret@example.neon.tech/fieldpilot"
        "?ssl=require"
    )


def test_non_postgres_database_url_is_preserved() -> None:
    raw = "sqlite+aiosqlite:///./fieldpilot.db"

    settings = Settings(database_url=raw, _env_file=None)

    assert settings.database_url == raw

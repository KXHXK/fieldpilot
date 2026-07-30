from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.base import Base


engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url == "sqlite+aiosqlite:///:memory:":
    engine_options.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

engine = create_async_engine(settings.database_url, **engine_options)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def create_database_schema() -> None:
    from app.db import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_database_schema() -> None:
    from app.db import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

import os
import sys
from pathlib import Path

os.environ.setdefault("USE_MOCK_LLM", "true")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_AUTO_CREATE"] = "false"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest_asyncio

from app.db import create_database_schema, drop_database_schema


@pytest_asyncio.fixture(autouse=True)
async def reset_database_schema():
    await drop_database_schema()
    await create_database_schema()
    yield
    await drop_database_schema()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.health import router as health_router
from app.api.missions import router as missions_router
from app.config import settings
from app.db import create_database_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_auto_create:
        await create_database_schema()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FieldPilot 外勤任务编排 API：类型化语义入口、确定性规划、独立校验与状态化重规划。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
)
app.include_router(health_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(missions_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "FieldPilot API", "docs": "/docs", "health": "/api/health"}

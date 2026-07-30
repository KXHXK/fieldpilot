from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.field_task import router as field_task_router
from app.api.health import router as health_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="城市外勤任务编排 Agent 的可运行 MVP。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(health_router, prefix="/api")
app.include_router(field_task_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "FieldPilot API", "docs": "/docs", "health": "/api/health"}

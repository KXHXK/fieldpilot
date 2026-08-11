from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db_session

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "fieldpilot",
        "version": settings.app_version,
        "local_route_provider": settings.local_route_provider,
        "agent_mode": "mock" if settings.use_mock_llm else "live",
    }


@router.get("/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str | bool]:
    await session.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "database": "reachable",
        "local_route_provider": settings.local_route_provider,
        "amap_key_configured": bool(settings.amap_api_key),
        "llm_key_configured": bool(settings.openai_api_key),
        "manual_inventory_configured": bool(settings.manual_candidate_file),
    }

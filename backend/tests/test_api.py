import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_checks_database() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "reachable",
        "local_route_provider": "fixture",
        "amap_key_configured": False,
        "llm_key_configured": False,
        "manual_inventory_configured": False,
    }


@pytest.mark.asyncio
async def test_legacy_field_task_endpoint_is_removed() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/field-task/plan", json={})

    assert response.status_code == 404

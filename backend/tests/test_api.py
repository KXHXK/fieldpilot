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
    }


@pytest.mark.asyncio
async def test_create_field_task_plan() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/field-task/plan",
            json={
                "city": "上海",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "industry": "新能源汽车",
                "target_place_types": ["品牌门店", "核心商圈"],
                "objective": "调研品牌门店分布与周边竞品",
                "budget": 3000,
                "transport_type": "public_transport",
                "base_preference": "靠近地铁，便于覆盖多个商圈",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "上海"
    assert len(payload["days"]) == 3
    assert payload["tool_statuses"]

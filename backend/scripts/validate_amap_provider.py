from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.domain import LocationInput, MealType, SourceMode
from app.providers.amap import AmapLocalRouteProvider
from app.providers.fixture import FixtureCandidateProvider


async def validate(output: Path) -> None:
    if not settings.amap_api_key:
        raise SystemExit("AMAP_API_KEY is required for live provider validation")
    provider = AmapLocalRouteProvider(
        api_key=settings.amap_api_key,
        fallback=FixtureCandidateProvider(),
        base_url=settings.amap_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
        max_concurrency=settings.provider_max_concurrency,
        max_live_calls=min(settings.provider_max_live_calls, 12),
    )
    try:
        origin = LocationInput(
            name="西湖区客户现场",
            address="杭州市西湖区文三路",
            city="杭州",
        )
        destination = LocationInput(
            name="滨江区工作地点",
            address="杭州市滨江区江南大道",
            city="杭州",
        )
        depart_at = datetime.now(ZoneInfo("Asia/Shanghai")).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        routes = await provider.local_routes(
            "manual-validation-origin",
            "manual-validation-destination",
            origin,
            destination,
            depart_at,
            ["transit", "taxi", "walking"],
        )
        meals = await provider.nearby_meals(
            "manual-validation-origin",
            origin,
            MealType.LUNCH,
            120,
        )
        route_live = [item for item in routes if item.source_mode == SourceMode.LIVE]
        meal_live = [item for item in meals if item.source_mode == SourceMode.LIVE]
        if not route_live or not meal_live:
            raise SystemExit(
                "live Amap validation failed: route or meal results used fallback"
            )
        snapshots = provider.provider_snapshots()
        report = {
            "status": "passed",
            "validated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "provider": provider.provider_name,
            "route_live_count": len(route_live),
            "route_modes": sorted({item.mode.value for item in route_live}),
            "meal_live_count": len(meal_live),
            "snapshot_summaries": [
                {
                    "capability": item.capability,
                    "source_mode": item.source_mode.value,
                    "query_fingerprint": item.query_fingerprint,
                    "fetched_at": item.fetched_at.isoformat(),
                    "expires_at": item.expires_at.isoformat()
                    if item.expires_at
                    else None,
                }
                for item in snapshots
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))
    finally:
        await provider.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a minimal live Amap route and meal validation without persisting keys."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/amap-provider-validation.json"),
    )
    args = parser.parse_args()
    asyncio.run(validate(args.output))


if __name__ == "__main__":
    main()

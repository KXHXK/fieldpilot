from datetime import date

import pytest
from pydantic import ValidationError

from app.models import FieldTaskRequest


def test_request_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="结束日期不能早于开始日期"):
        FieldTaskRequest(
            city="上海",
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 1),
            industry="新能源汽车",
            target_place_types=["品牌门店"],
            objective="调研品牌门店分布与周边竞品",
            budget=3000,
        )


def test_request_deduplicates_target_types() -> None:
    request = FieldTaskRequest(
        city="上海",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        industry="新能源汽车",
        target_place_types=["品牌门店", " 品牌门店 ", "核心商圈"],
        objective="调研品牌门店分布与周边竞品",
        budget=3000,
    )
    assert request.target_place_types == ["品牌门店", "核心商圈"]

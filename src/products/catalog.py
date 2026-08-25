"""추천 전 상품 후보를 조건으로 좁히는 읽기 전용 카탈로그."""

from __future__ import annotations

from typing import Any


RECOMMENDATION_REQUIRED_FIELDS = {
    "age": "나이",
    "employment_status": "고용 형태",
    "risk_preference": "투자 위험 선호",
    "goal": "연금 준비 목적",
}


def missing_recommendation_fields(user_conditions: dict[str, Any]) -> list[str]:
    """데모 추천 정책에 꼭 필요한 고객 조건만 반환한다."""
    return [
        label
        for key, label in RECOMMENDATION_REQUIRED_FIELDS.items()
        if user_conditions.get(key) in (None, "")
    ]

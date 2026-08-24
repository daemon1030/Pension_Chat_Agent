"""추천 전 상품 후보를 조건으로 좁히는 읽기 전용 카탈로그."""

from __future__ import annotations

import json
from pathlib import Path
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


def load_products(path: Path | str) -> list[dict[str, Any]]:
    """상품 조건 데이터를 읽는다. 실제 DB 도입 전 JSON 기반 MVP 저장소다."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"상품 카탈로그 파일이 없습니다: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    products = data.get("products", [])
    if not isinstance(products, list):
        raise ValueError("상품 카탈로그의 products는 목록이어야 합니다.")
    return [product for product in products if isinstance(product, dict)]


def filter_products(products: list[dict[str, Any]], user_conditions: dict[str, Any]) -> list[dict[str, Any]]:
    """명시된 가입·위험·목적 조건과 맞지 않는 상품을 제외한다."""
    age = user_conditions.get("age")
    matches: list[dict[str, Any]] = []
    for product in products:
        if product.get("status") != "ACTIVE":
            continue
        if not isinstance(age, int) or age < int(product.get("min_age", 0)):
            continue
        if user_conditions.get("employment_status") not in product.get("allowed_employment", []):
            continue
        if user_conditions.get("risk_preference") not in product.get("allowed_risk_preferences", []):
            continue
        if user_conditions.get("goal") not in product.get("goals", []):
            continue
        matches.append(product)
    return matches

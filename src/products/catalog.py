"""추천 전 상품 후보를 조건으로 좁히는 읽기 전용 카탈로그."""

from __future__ import annotations

from typing import Any


RECOMMENDATION_REQUIRED_FIELDS = {
    "account_type": "계좌 유형",
    "risk_preference": "투자 위험 선호",
}

# 상품 클래스의 위험등급은 1이 가장 높고 6이 가장 낮다. 이 값은 사용자의
# 위험 선호를 DB 조회 조건으로 바꾸는 기준이므로, 한 곳에서만 관리한다.
RISK_GRADE_RANGES = {
    "CONSERVATIVE": (5, 6),
    "BALANCED": (3, 4),
    "AGGRESSIVE": (1, 3),
}

RISK_GRADE_LABELS = {
    1: "매우 높은 위험",
    2: "높은 위험",
    3: "다소 높은 위험",
    4: "보통 위험",
    5: "낮은 위험",
    6: "매우 낮은 위험",
}

ACCOUNT_TYPE_LABELS = {
    "PENSION_SAVINGS": "연금저축계좌",
    "IRP": "IRP",
    "RETIREMENT_PENSION": "퇴직연금",
}

SALES_CHANNEL_LABELS = {
    "ONLINE": "온라인",
    "OFFLINE": "오프라인",
    "ONLINE_SUPER": "온라인슈퍼",
}


def missing_recommendation_fields(user_conditions: dict[str, Any]) -> list[str]:
    """상품 추천에 필요한 최소 조건만 반환한다.

    현재 상품 클래스 DB에서 직접 비교 가능한 필수값은 계좌 유형과 위험 선호다.
    투자 기간·목적은 추천 설명을 보완하는 선택 정보이며, 없다고 후보 검색을
    막지 않는다. 나이·소득·고용 형태는 계좌·세제 추천에서 추가로 필요할 수
    있지만, 현재 상품 클래스 필터의 필수값은 아니다.
    """
    missing = [
        label
        for key, label in RECOMMENDATION_REQUIRED_FIELDS.items()
        if user_conditions.get(key) in (None, "")
    ]
    return missing


def risk_grade_range(risk_preference: str) -> tuple[int, int]:
    """사용자 위험 선호에 해당하는 상품 위험등급 범위를 반환한다."""
    try:
        return RISK_GRADE_RANGES[risk_preference]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 투자 위험 선호입니다: {risk_preference}") from error


def enrich_candidate_classes(
    candidates: list[dict[str, Any]], user_conditions: dict[str, Any]
) -> list[dict[str, Any]]:
    """후보 클래스에 코드로 확인 가능한 조건 일치 이유만 추가한다.

    사용자 조건 전체는 별도로 최종 LLM에 전달한다. 이 함수는 DB 컬럼과 직접
    비교할 수 있는 사실만 ``matched_conditions``로 확정해, 근거 없는 적합성
    설명이 만들어지지 않게 한다.
    """
    enriched = []
    for candidate in candidates:
        item = {
            key: value
            for key, value in candidate.items()
            if value is not None and value != "" and value != []
        }
        matches = []
        account_type = user_conditions.get("account_type")
        eligible_accounts = item.get("eligible_account_types", [])
        if account_type and account_type in eligible_accounts:
            matches.append({
                "type": "ACCOUNT_TYPE",
                "user_value": account_type,
                "candidate_value": eligible_accounts,
                "message": f"{ACCOUNT_TYPE_LABELS[account_type]}에서 가입 가능한 클래스입니다.",
            })

        risk_preference = user_conditions.get("risk_preference")
        risk_grade = item.get("risk_grade")
        if risk_preference and risk_grade is not None:
            minimum, maximum = risk_grade_range(risk_preference)
            if minimum <= risk_grade <= maximum:
                matches.append({
                    "type": "RISK_PREFERENCE",
                    "user_value": risk_preference,
                    "candidate_value": risk_grade,
                    "message": f"선호 위험 범위에 해당하는 {risk_grade}등급({RISK_GRADE_LABELS.get(risk_grade, '위험등급')}) 상품입니다.",
                })

        sales_channel = user_conditions.get("sales_channel")
        if sales_channel and sales_channel == item.get("sales_channel"):
            matches.append({
                "type": "SALES_CHANNEL",
                "user_value": sales_channel,
                "candidate_value": sales_channel,
                "message": f"{SALES_CHANNEL_LABELS[sales_channel]} 가입이 가능한 클래스입니다.",
            })

        item["matched_conditions"] = matches
        enriched.append(item)
    return enriched

from src.products.catalog import (
    enrich_candidate_classes,
    missing_recommendation_fields,
    risk_grade_range,
)


def test_product_recommendation_requires_only_account_and_risk_preference():
    assert missing_recommendation_fields({
        "account_type": "IRP",
        "risk_preference": "CONSERVATIVE",
    }) == []
    assert missing_recommendation_fields({"risk_preference": "CONSERVATIVE"}) == ["계좌 유형"]


def test_risk_preference_maps_to_a_product_risk_grade_range():
    assert risk_grade_range("CONSERVATIVE") == (5, 6)
    assert risk_grade_range("BALANCED") == (3, 4)
    assert risk_grade_range("AGGRESSIVE") == (1, 3)


def test_candidate_reasons_are_added_only_for_direct_db_matches():
    candidates = enrich_candidate_classes([{
        "class_id": "BH807",
        "product_id": "B5517",
        "risk_grade": 6,
        "eligible_account_types": ["PENSION_SAVINGS"],
        "sales_channel": "ONLINE",
        "total_fee_rate": 0.185,
    }], {
        "age": 30,
        "annual_income": 50_000_000,
        "account_type": "PENSION_SAVINGS",
        "risk_preference": "CONSERVATIVE",
        "sales_channel": "ONLINE",
        "goal": "RETIREMENT_PREPARATION",
    })

    matches = candidates[0]["matched_conditions"]

    assert [match["type"] for match in matches] == [
        "ACCOUNT_TYPE", "RISK_PREFERENCE", "SALES_CHANNEL"
    ]
    assert candidates[0]["total_fee_rate"] == 0.185
    assert all("age" not in match for match in matches)

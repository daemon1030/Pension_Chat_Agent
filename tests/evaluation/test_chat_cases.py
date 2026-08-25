import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_chat_evaluation_cases_cover_the_expected_categories_and_count():
    path = PROJECT_ROOT / "data/evaluation/chat_test_queries.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(cases) == 30
    assert {case["category"] for case in cases} == {
        "PENSION_GENERAL_INFO",
        "PENSION_RECOMMENDATION_MISSING",
        "PENSION_RECOMMENDATION_MATCH",
        "PENSION_RECOMMENDATION_NO_MATCH",
    }
    assert len({case["case_id"] for case in cases}) == 30

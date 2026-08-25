from src.graph.nodes import analyze_query
from src.llm.schemas import QueryAnalysis


class FakeAnalysisClient:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def generate_query_analysis(self, *, system_prompt: str, user_prompt: str) -> QueryAnalysis:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return QueryAnalysis(
            is_pension_related=True,
            intent="PENSION_RECOMMENDATION",
            user_conditions={"age": 20, "risk_preference": "CONSERVATIVE"},
        )


def test_query_analysis_returns_only_the_generic_state_fields():
    client = FakeAnalysisClient()

    result = analyze_query({"query": "20살이고 안전한 연금을 추천해줘"}, client)

    assert result == {
        "is_pension_related": True,
        "scope": "IN_SCOPE",
        "intent": "PENSION_RECOMMENDATION",
        "user_conditions": {"age": 20, "risk_preference": "CONSERVATIVE"},
    }
    assert "[사용자 질문]" in client.user_prompt
    assert "추측하지 마세요" in client.system_prompt

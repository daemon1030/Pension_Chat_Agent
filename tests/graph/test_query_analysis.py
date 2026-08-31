from src.graph.nodes import (
    analyze_query,
    build_search_queries,
    search_with_queries,
    supplement_explicit_conditions,
)
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
            retrieval_sources=["PRODUCT_DB", "PRODUCT_RAG"],
            search_queries=["안정형 연금상품 추천"],
            user_conditions={"age": 20, "risk_preference": "CONSERVATIVE"},
        )


def test_query_analysis_returns_only_the_generic_state_fields():
    client = FakeAnalysisClient()

    result = analyze_query({"query": "20살이고 안전한 연금을 추천해줘"}, client)

    assert result == {
        "is_pension_related": True,
        "scope": "IN_SCOPE",
        "intent": "PENSION_RECOMMENDATION",
        "retrieval_sources": ["PRODUCT_DB", "PRODUCT_RAG"],
        "search_queries": ["안정형 연금상품 추천"],
        "user_conditions": {"age": 20, "risk_preference": "CONSERVATIVE"},
    }
    assert "[사용자 질문]" in client.user_prompt
    assert "추측하지 마세요" in client.system_prompt


def test_search_uses_the_original_question_and_deduplicated_generated_queries():
    class Chunk:
        def __init__(self, chunk_id: str, score: float) -> None:
            self.chunk_id = chunk_id
            self.score = score

    class Retriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def search(self, query: str, **_: object) -> list[Chunk]:
            self.queries.append(query)
            if query == "연금 언제 받아?":
                return [Chunk("same", 0.7)]
            return [Chunk("same", 0.8), Chunk("other", 0.6)]

    queries = build_search_queries("연금 언제 받아?", ["연금 수령 개시 요건", "연금 수령 개시 요건"])
    retriever = Retriever()

    chunks = search_with_queries(retriever, queries, top_k=5)

    assert queries == ["연금 언제 받아?", "연금 수령 개시 요건"]
    assert retriever.queries == queries
    assert [chunk.chunk_id for chunk in chunks] == ["same", "other"]
    assert chunks[0].score == 0.8


def test_explicit_account_and_risk_expressions_are_supplemented_without_overwriting_llm_values():
    assert supplement_explicit_conditions(
        "안정적인 IRP 투자를 하고 싶어요",
        {},
    ) == {"account_type": "IRP", "risk_preference": "CONSERVATIVE"}
    assert supplement_explicit_conditions(
        "IRP에서 안정적으로 운용하고 싶어요",
        {"risk_preference": "BALANCED"},
    ) == {"account_type": "IRP", "risk_preference": "BALANCED"}

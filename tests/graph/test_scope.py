from src.graph.nodes import check_scope, out_of_scope_response
from src.graph.workflow import create_postgres_clova_rag_workflow
from src.llm.schemas import QueryAnalysis


def test_non_pension_question_is_out_of_scope():
    result = out_of_scope_response({"query": "오늘 저녁밥 추천해줘"})

    assert check_scope({"query": "오늘 저녁밥 추천해줘"}) == {"scope": "OUT_OF_SCOPE"}
    assert result["status"] == "OUT_OF_SCOPE"
    assert result["sources"] == []


def test_pension_question_is_in_scope():
    assert check_scope({"query": "IRP 중도인출 조건이 뭐야?"}) == {"scope": "IN_SCOPE"}


class FailingEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        raise AssertionError("범위 밖 질문은 임베딩 API를 호출하면 안 됩니다.")


class FailingChatClient:
    def generate_rag_answer(self, **kwargs):
        raise AssertionError("범위 밖 질문은 최종 답변 API를 호출하면 안 됩니다.")


class LlmRejectingChatClient(FailingChatClient):
    def generate_query_analysis(self, **kwargs) -> QueryAnalysis:
        return QueryAnalysis(is_pension_related=False, intent=None)


class UnusedRepository:
    """범위 종료 테스트에서는 DB 조회가 일어나면 안 된다."""


def make_workflow(chat_client):
    return create_postgres_clova_rag_workflow(
        embedding_client=FailingEmbeddingClient(),
        chat_client=chat_client,
        repository=UnusedRepository(),
    )


def test_workflow_ends_before_external_calls_for_keyword_out_of_scope_question():
    result = make_workflow(FailingChatClient()).invoke({"query": "오늘 저녁밥 추천해줘"})

    assert result["status"] == "OUT_OF_SCOPE"


def test_workflow_ends_when_llm_rejects_keyword_matched_question():
    result = make_workflow(LlmRejectingChatClient()).invoke(
        {"query": "연금이라는 단어가 포함된 뉴스 제목만 고쳐줘"}
    )

    assert result["status"] == "OUT_OF_SCOPE"
    assert result["is_pension_related"] is False

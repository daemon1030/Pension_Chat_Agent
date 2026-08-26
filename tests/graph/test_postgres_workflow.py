from src.graph.workflow import create_postgres_clova_rag_workflow
from src.llm.schemas import QueryAnalysis, RagAnswer


class FakeEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeChatClient:
    def __init__(self, analysis: QueryAnalysis) -> None:
        self.analysis = analysis
        self.answer_prompts: list[str] = []

    def generate_query_analysis(self, **kwargs) -> QueryAnalysis:
        return self.analysis

    def generate_rag_answer(self, *, user_prompt: str, **kwargs) -> RagAnswer:
        self.answer_prompts.append(user_prompt)
        return RagAnswer(status="ANSWER", answer="DB 근거 기반 답변입니다.")


class FakeRepository:
    def __init__(self) -> None:
        self.search_calls = []

    def filter_products(self, user_conditions):
        return [{
            "product_id": "PENSION_PRODUCT_DEMO_001",
            "product_name": "안정형 데모 상품",
            "status": "ACTIVE",
        }]

    def search_chunks(self, embedding, **kwargs):
        self.search_calls.append(kwargs)
        is_product = kwargs["knowledge_type"] == "PRODUCT"
        return [{
            "chunk_id": "PRODUCT_001_CHUNK001" if is_product else "POLICY_001_CHUNK001",
            "document_id": "PRODUCT_001" if is_product else "POLICY_001",
            "document_title": "데모 상품" if is_product else "연금 규정",
            "section_id": "SEC_001", "section_title": "개요", "topic": "연금",
            "content": "상품 설명" if is_product else "규정 설명",
            "page_start": 1, "page_end": 1, "validation_status": "PASS",
            "product_id": "PENSION_PRODUCT_DEMO_001" if is_product else None,
            "score": 0.9,
        }]


def test_postgres_recommendation_workflow_filters_products_before_product_vector_search():
    repository = FakeRepository()
    workflow = create_postgres_clova_rag_workflow(
        embedding_client=FakeEmbeddingClient(),
        chat_client=FakeChatClient(QueryAnalysis(
            is_pension_related=True,
            intent="PENSION_RECOMMENDATION",
            retrieval_sources=["PRODUCT_DB", "PRODUCT_RAG"],
            user_conditions={
                "age": 20,
                "employment_status": "EMPLOYED",
                "risk_preference": "CONSERVATIVE",
                "goal": "RETIREMENT_PREPARATION",
            },
        )),
        repository=repository,
    )

    result = workflow.invoke({"query": "안전한 연금상품을 추천해줘"})

    assert result["candidate_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]
    assert result["sources"][0]["document_id"] == "PRODUCT_001"
    assert repository.search_calls[0]["knowledge_type"] == "PRODUCT"
    assert repository.search_calls[0]["allowed_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]


def test_postgres_information_workflow_searches_only_policy_vectors():
    repository = FakeRepository()
    workflow = create_postgres_clova_rag_workflow(
        embedding_client=FakeEmbeddingClient(),
        chat_client=FakeChatClient(QueryAnalysis(
            is_pension_related=True,
            intent="PENSION_INFO",
            retrieval_sources=["POLICY_RAG"],
        )),
        repository=repository,
    )

    result = workflow.invoke({"query": "연금저축이 뭐야?"})

    assert result["sources"][0]["document_id"] == "POLICY_001"
    assert repository.search_calls[0]["knowledge_type"] == "POLICY"
    assert repository.search_calls[0]["allowed_product_ids"] is None


def test_information_workflow_uses_the_product_rag_selected_by_llm():
    repository = FakeRepository()
    workflow = create_postgres_clova_rag_workflow(
        embedding_client=FakeEmbeddingClient(),
        chat_client=FakeChatClient(QueryAnalysis(
            is_pension_related=True,
            intent="PENSION_INFO",
            retrieval_sources=["PRODUCT_RAG"],
        )),
        repository=repository,
    )

    result = workflow.invoke({"query": "안정형 연금상품의 특징은?"})

    assert result["sources"][0]["document_id"] == "PRODUCT_001"
    assert repository.search_calls[0]["knowledge_type"] == "PRODUCT"
    assert repository.search_calls[0]["allowed_product_ids"] is None

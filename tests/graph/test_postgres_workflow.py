from src.graph.workflow import create_postgres_clova_rag_workflow
from src.graph.nodes import rank_recommended_products, store_candidate_products
from src.llm.schemas import QueryAnalysis, RagAnswer


class FakeEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeChatClient:
    def __init__(self, analysis: QueryAnalysis) -> None:
        self.analysis = analysis
        self.analysis_calls = 0
        self.answer_prompts: list[str] = []

    def generate_query_analysis(self, **kwargs) -> QueryAnalysis:
        self.analysis_calls += 1
        return self.analysis

    def generate_rag_answer(self, *, user_prompt: str, **kwargs) -> RagAnswer:
        self.answer_prompts.append(user_prompt)
        return RagAnswer(status="ANSWER", answer="DB 근거 기반 답변입니다.")


class FakeRepository:
    def __init__(self) -> None:
        self.search_calls = []

    def filter_product_classes(self, user_conditions):
        return [{
            "class_id": "CLASS_DEMO_001",
            "class_name": "C-퇴직e",
            "product_id": "PENSION_PRODUCT_DEMO_001",
            "product_name": "안정형 데모 상품",
            "status": "ON_SALE",
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
                "account_type": "IRP",
                "risk_preference": "CONSERVATIVE",
                "goal": "RETIREMENT_PREPARATION",
            },
        )),
        repository=repository,
    )

    result = workflow.invoke({"query": "안전한 연금상품을 추천해줘"})

    assert result["candidate_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]
    assert result["recommended_products"][0]["product_id"] == "PENSION_PRODUCT_DEMO_001"
    assert result["sources"][0]["document_id"] == "PRODUCT_001"
    assert repository.search_calls[0]["knowledge_type"] == "PRODUCT"
    assert repository.search_calls[0]["allowed_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]
    assert repository.search_calls[0]["per_product_limit"] == 2


def test_recommendation_with_missing_conditions_returns_the_fixed_follow_up():
    repository = FakeRepository()
    workflow = create_postgres_clova_rag_workflow(
        embedding_client=FakeEmbeddingClient(),
        chat_client=FakeChatClient(QueryAnalysis(
            is_pension_related=True,
            intent="PENSION_RECOMMENDATION",
            retrieval_sources=["PRODUCT_DB", "PRODUCT_RAG"],
            user_conditions={"risk_preference": "CONSERVATIVE"},
        )),
        repository=repository,
    )

    result = workflow.invoke({"query": "안전한 연금상품을 추천해줘"})

    assert result["status"] == "NEED_MORE_INFO"
    assert result["missing_fields"] == ["계좌 유형"]
    assert result["follow_up_question"] == (
        "어느 계좌에서 운용할 예정인지와 "
        "안정성·수익성 중 선호하는 방향을 알려주세요."
    )
    assert repository.search_calls == []


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


def test_workflow_uses_separate_clients_for_analysis_and_final_answer():
    repository = FakeRepository()
    analysis_client = FakeChatClient(QueryAnalysis(
        is_pension_related=True,
        intent="PENSION_INFO",
        retrieval_sources=["POLICY_RAG"],
    ))
    answer_client = FakeChatClient(QueryAnalysis(
        is_pension_related=False,
        intent=None,
    ))
    workflow = create_postgres_clova_rag_workflow(
        embedding_client=FakeEmbeddingClient(),
        analysis_chat_client=analysis_client,
        answer_chat_client=answer_client,
        repository=repository,
    )

    result = workflow.invoke({"query": "연금저축이 뭐야?"})

    assert result["status"] == "ANSWER"
    assert analysis_client.analysis_calls == 1
    assert analysis_client.answer_prompts == []
    assert answer_client.analysis_calls == 0
    assert len(answer_client.answer_prompts) == 1


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


def test_recommendation_ranking_keeps_one_entry_per_product_and_two_evidence_chunks():
    class Chunk:
        def __init__(self, chunk_id, product_id, score):
            self.chunk_id = chunk_id
            self.product_id = product_id
            self.score = score

        def to_dict(self):
            return {"chunk_id": self.chunk_id, "product_id": self.product_id, "score": self.score}

    candidates = [
        {"class_id": "A1", "product_id": "A", "product_name": "상품 A"},
        {"class_id": "A2", "product_id": "A", "product_name": "상품 A"},
        {"class_id": "B1", "product_id": "B", "product_name": "상품 B"},
        {"class_id": "C1", "product_id": "C", "product_name": "상품 C"},
    ]
    chunks = [
        Chunk("A-1", "A", 0.90), Chunk("A-2", "A", 0.80), Chunk("A-3", "A", 0.70),
        Chunk("B-1", "B", 0.85), Chunk("B-2", "B", 0.75),
        Chunk("C-1", "C", 0.60),
    ]

    products, evidence = rank_recommended_products(candidates, chunks)

    assert [product["product_id"] for product in products] == ["A", "B", "C"]
    assert products[0]["supporting_chunk_ids"] == ["A-1", "A-2"]
    assert [chunk.chunk_id for chunk in evidence] == ["A-1", "A-2", "B-1", "B-2", "C-1"]


def test_candidate_storage_limits_the_db_pool_to_twenty_unique_products():
    candidates = [
        {"class_id": f"C{index}", "product_id": f"P{index}", "product_name": f"상품 {index}"}
        for index in range(25)
    ]

    stored = store_candidate_products(candidates, {"account_type": "IRP"})

    assert len(stored["candidate_product_ids"]) == 20
    assert stored["candidate_product_ids"] == [f"P{index}" for index in range(20)]

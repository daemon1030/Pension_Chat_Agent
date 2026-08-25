from src.rag.postgres_retriever import PostgresRagRetriever


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]


class FakeRepository:
    def __init__(self) -> None:
        self.calls = []

    def search_chunks(self, embedding, **kwargs):
        self.calls.append((embedding, kwargs))
        return [{
            "chunk_id": "PRODUCT_001_CHUNK001", "document_id": "PRODUCT_001",
            "document_title": "데모 상품", "section_id": "SEC_001", "section_title": "개요",
            "topic": "상품", "content": "상품 설명", "page_start": 1, "page_end": 1,
            "validation_status": "PASS", "product_id": "PENSION_PRODUCT_DEMO_001", "score": 0.9,
        }]


def test_postgres_product_retriever_filters_with_candidate_product_ids():
    repository = FakeRepository()
    client = FakeEmbeddingClient()
    retriever = PostgresRagRetriever(repository, client, knowledge_type="PRODUCT")

    result = retriever.search("안전한 상품", allowed_product_ids={"PENSION_PRODUCT_DEMO_001"})

    assert result[0].product_id == "PENSION_PRODUCT_DEMO_001"
    assert repository.calls[0][1]["knowledge_type"] == "PRODUCT"
    assert repository.calls[0][1]["allowed_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]


def test_postgres_product_retriever_skips_embedding_when_no_candidate_exists():
    repository = FakeRepository()
    client = FakeEmbeddingClient()
    retriever = PostgresRagRetriever(repository, client, knowledge_type="PRODUCT")

    assert retriever.search("안전한 상품", allowed_product_ids=set()) == []
    assert client.calls == []
    assert repository.calls == []

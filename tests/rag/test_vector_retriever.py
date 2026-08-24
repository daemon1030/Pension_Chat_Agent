import json

from src.rag.vector_retriever import EmbeddedJsonRagRetriever


class FakeEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0] if "연금" in text else [0.0, 1.0]


def test_vector_retriever_uses_embedding_similarity(tmp_path):
    path = tmp_path / "embeddings.jsonl"
    records = [
        {"chunk_id": "A", "document_id": "DOC_001", "document_title": "연금", "section_id": "SEC_001", "section_title": "수령", "topic": "연금", "content": "연금 수령", "page_start": 1, "page_end": 1, "validation_status": "PASS", "embedding": [1.0, 0.0]},
        {"chunk_id": "B", "document_id": "DOC_002", "document_title": "기타", "section_id": "SEC_001", "section_title": "기타", "topic": "기타", "content": "기타 내용", "page_start": 1, "page_end": 1, "validation_status": "PASS", "embedding": [0.0, 1.0]},
    ]
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records), encoding="utf-8")

    result = EmbeddedJsonRagRetriever.from_jsonl(path, FakeEmbeddingClient()).search("연금 언제 받나요?", top_k=1)

    assert result[0].chunk_id == "A"
    assert "product_id" not in result[0].to_dict()


def test_vector_retriever_preserves_optional_product_id(tmp_path):
    path = tmp_path / "product_embeddings.jsonl"
    record = {
        "chunk_id": "PRODUCT_001_OVERVIEW_CHUNK001",
        "document_id": "PRODUCT_001",
        "document_title": "예시 안정형 연금상품 안내서",
        "section_id": "OVERVIEW",
        "section_title": "상품 개요",
        "topic": "안정형 연금상품 특징",
        "content": "예시용 상품 설명입니다.",
        "page_start": 1,
        "page_end": 1,
        "validation_status": "PASS",
        "product_id": "PENSION_PRODUCT_DEMO_001",
        "embedding": [1.0, 0.0],
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = EmbeddedJsonRagRetriever.from_jsonl(path, FakeEmbeddingClient()).search("연금상품", top_k=1)

    assert result[0].product_id == "PENSION_PRODUCT_DEMO_001"
    assert result[0].to_dict()["product_id"] == "PENSION_PRODUCT_DEMO_001"

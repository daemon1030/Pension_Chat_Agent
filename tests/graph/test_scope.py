import json

from src.graph.nodes import check_scope, out_of_scope_response
from src.graph.workflow import create_clova_rag_workflow


def test_non_pension_question_is_out_of_scope():
    result = out_of_scope_response({"query": "오늘 저녁밥 추천해줘"})

    assert check_scope({"query": "오늘 저녁밥 추천해줘"}) == {"scope": "OUT_OF_SCOPE"}
    assert result["status"] == "OUT_OF_SCOPE"
    assert result["sources"] == []


def test_pension_question_is_in_scope():
    assert check_scope({"query": "IRP 중도인출 조건이 뭐야?"}) == {"scope": "IN_SCOPE"}


class FailingClient:
    def embed(self, text: str) -> list[float]:
        raise AssertionError("범위 밖 질문은 임베딩 API를 호출하면 안 됩니다.")


class FailingChatClient:
    def generate_rag_answer(self, **kwargs):
        raise AssertionError("범위 밖 질문은 Chat API를 호출하면 안 됩니다.")


def test_workflow_ends_before_external_calls_for_out_of_scope_question(tmp_path):
    path = tmp_path / "embeddings.jsonl"
    product_path = tmp_path / "product_embeddings.jsonl"
    catalog_path = tmp_path / "products.json"
    path.write_text(json.dumps({
        "chunk_id": "C1", "document_id": "DOC_001", "document_title": "연금", "section_id": "SEC_001",
        "section_title": "연금", "topic": "연금", "content": "연금 안내", "page_start": 1,
        "page_end": 1, "validation_status": "PASS", "embedding": [1.0],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    product_path.write_text(json.dumps({
        "chunk_id": "P1", "document_id": "PRODUCT_001", "document_title": "데모 상품", "section_id": "SEC_001",
        "section_title": "개요", "topic": "상품", "content": "데모 상품", "page_start": 1,
        "page_end": 1, "validation_status": "PASS", "product_id": "PENSION_PRODUCT_DEMO_001", "embedding": [1.0],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    catalog_path.write_text('{"products": []}', encoding="utf-8")

    workflow = create_clova_rag_workflow(
        path,
        FailingClient(),
        FailingChatClient(),
        product_embedding_path=product_path,
        product_catalog_path=catalog_path,
    )
    result = workflow.invoke({"query": "오늘 저녁밥 추천해줘"})

    assert result["status"] == "OUT_OF_SCOPE"

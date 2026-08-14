import json

from src.graph.workflow import create_rag_workflow


def test_workflow_returns_only_retrieved_content_and_sources(tmp_path):
    content = "연금수령은 만 55세 이후에 가능합니다."
    (tmp_path / "DOC_001_rag_ready.json").write_text(json.dumps({"rag_data": [
        {"chunk_id": "C1", "document_id": "DOC_001", "document_title": "연금 안내", "section_id": "SEC_001", "section_title": "연금수령", "topic": "수령 조건", "content": content, "page_start": 3, "page_end": 3, "validation_status": "PASS"},
    ]}, ensure_ascii=False), encoding="utf-8")

    result = create_rag_workflow(tmp_path).invoke({"query": "연금은 언제 받을 수 있나요?"})

    assert result["status"] == "ANSWER"
    assert content in result["answer"]
    assert result["sources"] == [{"document_id": "DOC_001", "document_title": "연금 안내", "section_id": "SEC_001", "page": 3, "validation_status": "PASS"}]


def test_workflow_does_not_answer_without_grounded_context(tmp_path):
    (tmp_path / "DOC_001_rag_ready.json").write_text('{"rag_data": []}', encoding="utf-8")

    result = create_rag_workflow(tmp_path).invoke({"query": "가상화폐 수익을 보장해줘"})

    assert result["status"] == "NO_GROUNDED_CONTEXT"
    assert result["sources"] == []

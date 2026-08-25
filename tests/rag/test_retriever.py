import json

from src.rag.retriever import load_rag_chunks


def test_rag_chunk_loader_reads_ready_documents(tmp_path):
    (tmp_path / "DOC_001_rag_ready.json").write_text(json.dumps({"rag_data": [
        {"chunk_id": "C1", "document_id": "DOC_001", "document_title": "연금 안내", "section_id": "SEC_001", "section_title": "중도인출", "topic": "중도인출 조건", "content": "IRP 중도인출은 법정 사유가 필요합니다.", "page_start": 1, "page_end": 1, "validation_status": "PASS"},
        {"chunk_id": "C2", "document_id": "DOC_001", "document_title": "연금 안내", "section_id": "SEC_002", "section_title": "세액공제", "topic": "세액공제", "content": "세액공제 납입한도를 안내합니다.", "page_start": 2, "page_end": 2, "validation_status": "PASS"},
    ]}, ensure_ascii=False), encoding="utf-8")

    result = load_rag_chunks(tmp_path)

    assert [chunk.section_id for chunk in result] == ["SEC_001", "SEC_002"]
    assert result[0].document_id == "DOC_001"

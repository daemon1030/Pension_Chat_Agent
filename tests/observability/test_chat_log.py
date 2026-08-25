import json

from src.observability.chat_log import append_chat_log


def test_chat_log_records_query_and_answer(tmp_path):
    path = tmp_path / "chat.jsonl"

    append_chat_log(
        query="IRP가 뭐야?",
        result={
            "status": "ANSWER",
            "answer": "개인형퇴직연금입니다.",
            "missing_fields": [],
            "follow_up_question": None,
            "sources": [{"document_id": "DOC_001"}],
            "retrieved_chunks": [{
                "chunk_id": "DOC_001_SEC_001_CHUNK001",
                "document_id": "DOC_001",
                "section_id": "SEC_001",
                "product_id": None,
                "score": 0.82,
            }],
        },
        source="test",
        path=path,
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["query"] == "IRP가 뭐야?"
    assert record["answer"] == "개인형퇴직연금입니다."
    assert record["status"] == "ANSWER"
    assert record["retrieved_chunks"] == [{
        "chunk_id": "DOC_001_SEC_001_CHUNK001",
        "document_id": "DOC_001",
        "section_id": "SEC_001",
        "product_id": None,
        "score": 0.82,
    }]
    assert record["error"] is None


def test_chat_log_records_error_when_answer_generation_fails(tmp_path):
    path = tmp_path / "chat.jsonl"

    append_chat_log(query="연금 추천", error=ValueError("응답 형식 오류"), source="test", path=path)

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["status"] == "ERROR"
    assert record["answer"] is None
    assert record["retrieved_chunks"] == []
    assert "ValueError" in record["error"]

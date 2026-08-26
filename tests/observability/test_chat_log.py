import json

from src.observability.chat_log import append_chat_log


def test_chat_log_records_query_and_answer(tmp_path):
    path = tmp_path / "chat.jsonl"

    append_chat_log(
        query="IRP가 뭐야?",
        result={
            "scope": "IN_SCOPE",
            "is_pension_related": True,
            "intent": "PENSION_INFO",
            "retrieval_sources": ["POLICY_RAG"],
            "user_conditions": {"age": 20},
            "answer_generation_prompt": "[사용자 질문]\\nIRP가 뭐야?\\n\\n[검색 근거]\\n...",
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

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    analysis, final_response = records
    assert len(records) == 2
    assert analysis["stage"] == "QUERY_ANALYSIS"
    assert analysis["input"] == {"query": "IRP가 뭐야?"}
    assert analysis["output"] == {
        "scope": "IN_SCOPE",
        "is_pension_related": True,
        "intent": "PENSION_INFO",
        "retrieval_sources": ["POLICY_RAG"],
        "user_conditions": {"age": 20},
    }
    assert analysis["request_id"] == final_response["request_id"]
    assert final_response["stage"] == "FINAL_RESPONSE"
    assert final_response["input"]["answer_generation_prompt"].startswith("[사용자 질문]")
    assert final_response["output"]["answer"] == "개인형퇴직연금입니다."
    assert final_response["output"]["status"] == "ANSWER"
    assert final_response["input"]["retrieved_chunks"] == [{
        "chunk_id": "DOC_001_SEC_001_CHUNK001",
        "document_id": "DOC_001",
        "section_id": "SEC_001",
        "product_id": None,
        "score": 0.82,
    }]
    assert final_response["error"] is None


def test_chat_log_records_error_when_answer_generation_fails(tmp_path):
    path = tmp_path / "chat.jsonl"

    append_chat_log(query="연금 추천", error=ValueError("응답 형식 오류"), source="test", path=path)

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[1]["output"]["status"] == "ERROR"
    assert records[1]["output"]["answer"] is None
    assert records[1]["input"]["retrieved_chunks"] == []
    assert "ValueError" in records[1]["error"]

"""챗봇 요청과 응답을 JSONL 감사 로그로 남긴다."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


_WRITE_LOCK = Lock()


def _retrieval_log_entries(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """최종 State의 검색 결과에서 디버깅에 필요한 식별자와 점수만 남긴다."""
    if not result:
        return []
    entries = []
    for chunk in result.get("retrieved_chunks", []):
        entries.append({
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "section_id": chunk.get("section_id"),
            "product_id": chunk.get("product_id"),
            "score": chunk.get("score"),
        })
    return entries


def append_chat_log(
    *,
    query: str,
    result: dict[str, Any] | None = None,
    error: Exception | None = None,
    source: str,
    path: Path | str = "data/logs/chat_interactions.jsonl",
) -> None:
    """한 요청을 분석 단계와 최종 응답 단계의 두 JSONL 행으로 기록한다."""
    request_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    error_message = f"{type(error).__name__}: {error}" if error else None
    raw_llm_response = getattr(error, "last_response", None) if error else None
    records = [
        {
            "timestamp": timestamp,
            "request_id": request_id,
            "stage": "QUERY_ANALYSIS",
            "source": source,
            "input": {"query": query},
            "output": {
                "scope": result.get("scope") if result else None,
                "is_pension_related": result.get("is_pension_related") if result else None,
                "intent": result.get("intent") if result else None,
                "retrieval_sources": result.get("retrieval_sources", []) if result else [],
                "search_queries": result.get("search_queries", []) if result else [],
                "user_conditions": result.get("user_conditions", {}) if result else {},
            },
            "error": error_message,
            "raw_llm_response": raw_llm_response,
        },
        {
            "timestamp": timestamp,
            "request_id": request_id,
            "stage": "FINAL_RESPONSE",
            "source": source,
            "input": {
                "answer_generation_prompt": result.get("answer_generation_prompt") if result else None,
                "retrieved_chunks": _retrieval_log_entries(result),
            },
            "output": {
                "status": result.get("status") if result else "ERROR",
                "answer": result.get("answer") if result else None,
                "missing_fields": result.get("missing_fields", []) if result else [],
                "follow_up_question": result.get("follow_up_question") if result else None,
                "sources": result.get("sources", []) if result else [],
            },
            "error": error_message,
            "raw_llm_response": raw_llm_response,
        },
    ]
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK, log_path.open("a", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        output.flush()

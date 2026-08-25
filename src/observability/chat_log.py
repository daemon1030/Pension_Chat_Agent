"""챗봇 요청과 응답을 JSONL 감사 로그로 남긴다."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any


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
    """한 요청의 질문·응답 또는 오류를 한 JSONL 행으로 기록한다.

    로그에는 사용자가 입력한 내용이 포함될 수 있으므로 기본 경로는 Git에서
    제외된 data 디렉터리 아래로 둔다.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "query": query,
        "status": result.get("status") if result else "ERROR",
        "answer": result.get("answer") if result else None,
        "missing_fields": result.get("missing_fields", []) if result else [],
        "follow_up_question": result.get("follow_up_question") if result else None,
        "sources": result.get("sources", []) if result else [],
        "retrieved_chunks": _retrieval_log_entries(result),
        "error": f"{type(error).__name__}: {error}" if error else None,
    }
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK, log_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
        output.flush()

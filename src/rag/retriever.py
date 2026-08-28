"""RAG 청크 모델과 임베딩 생성용 파일 로더."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RagChunk:
    """검색 결과로 반환하는 RAG Chunk와 역추적 메타데이터."""

    chunk_id: str
    document_id: str
    document_title: str | None
    section_id: str
    section_title: str | None
    topic: str | None
    content: str
    page_start: int | None
    page_end: int | None
    validation_status: str
    product_id: str | None = None
    effective_date: str | None = None
    score: float = 0.0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RagChunk":
        return cls(
            chunk_id=value["chunk_id"],
            document_id=value["document_id"],
            document_title=value.get("document_title"),
            section_id=value["section_id"],
            section_title=value.get("section_title"),
            topic=value.get("topic"),
            content=value["content"],
            page_start=value.get("page_start"),
            page_end=value.get("page_end"),
            validation_status=value.get("validation_status", "NEEDS_REVIEW"),
            product_id=value.get("product_id"),
            effective_date=value.get("effective_date"),
            score=float(value.get("score", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "topic": self.topic,
            "content": self.content,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "validation_status": self.validation_status,
            "score": self.score,
        }
        if self.product_id is not None:
            result["product_id"] = self.product_id
        if self.effective_date is not None:
            result["effective_date"] = self.effective_date
        return result


def load_rag_chunks(directory: Path | str) -> list[RagChunk]:
    """임베딩 생성 전에 rag_ready JSON에서 확정 Chunk를 읽는다."""
    chunks: list[RagChunk] = []
    for path in sorted(Path(directory).glob("DOC_*_rag_ready.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks.extend(RagChunk.from_dict(item) for item in data.get("rag_data", []))
    return chunks

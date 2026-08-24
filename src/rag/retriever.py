"""임베딩 DB를 도입하기 전 rag_ready JSON을 검색하는 읽기 전용 검색기."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


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
        return result


class JsonRagRetriever:
    """``data/rag_ready``의 Chunk를 검색한다.

    현재는 외부 DB나 임베딩 모델을 사용하지 않는 한국어 문자 n-gram 기반 검색이다.
    호출 인터페이스를 유지하므로 이후 pgvector 검색기로 교체할 수 있다.
    """

    def __init__(self, chunks: list[RagChunk]) -> None:
        self._chunks = chunks

    @classmethod
    def from_directory(cls, directory: Path | str) -> "JsonRagRetriever":
        directory = Path(directory)
        chunks: list[RagChunk] = []
        for path in sorted(directory.glob("DOC_*_rag_ready.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            chunks.extend(RagChunk.from_dict(item) for item in data.get("rag_data", []))
        return cls(chunks)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text) if len(token) >= 2]

    @staticmethod
    def _bigrams(text: str) -> Counter[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        return Counter(normalized[index : index + 2] for index in range(max(len(normalized) - 1, 0)))

    def _score(self, query: str, chunk: RagChunk) -> float:
        query_tokens = set(self._tokens(query))
        query_bigrams = self._bigrams(query)
        if not query_tokens and not query_bigrams:
            return 0.0

        metadata = " ".join(filter(None, [chunk.document_title, chunk.section_title, chunk.topic]))
        searchable = f"{metadata}\n{chunk.content}"
        normalized = re.sub(r"\s+", "", searchable.lower())

        token_score = sum(1.0 for token in query_tokens if token in normalized)
        metadata_score = sum(2.0 for token in query_tokens if token in re.sub(r"\s+", "", metadata.lower()))
        chunk_bigrams = self._bigrams(searchable)
        shared_bigrams = sum(min(count, chunk_bigrams[bigram]) for bigram, count in query_bigrams.items())
        bigram_score = shared_bigrams / max(sum(query_bigrams.values()), 1)
        return token_score + metadata_score + bigram_score

    def search(self, query: str, *, top_k: int = 3) -> list[RagChunk]:
        if not query.strip() or top_k < 1:
            return []
        scored = [
            RagChunk(**{**chunk.__dict__, "score": self._score(query, chunk)})
            for chunk in self._chunks
        ]
        # 하나의 페이지에서 원문과 OCR이 중복된 경우가 있으므로, 같은
        # 문서·섹션·페이지에서는 가장 높은 점수의 Chunk만 남긴다.
        result: list[RagChunk] = []
        seen_sections: set[tuple[str, str, int | None]] = set()
        for chunk in sorted(scored, key=lambda item: item.score, reverse=True):
            if chunk.score <= 0:
                continue
            section_key = (chunk.document_id, chunk.section_id, chunk.page_start)
            if section_key in seen_sections:
                continue
            result.append(chunk)
            seen_sections.add(section_key)
            if len(result) == top_k:
                break
        return result

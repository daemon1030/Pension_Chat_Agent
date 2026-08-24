"""CLOVA 임베딩이 저장된 JSONL 파일을 검색하는 RAG 검색기."""

from __future__ import annotations

import json
import math
from pathlib import Path

from .naver_embedding import ClovaEmbeddingClient
from .retriever import RagChunk


class EmbeddedJsonRagRetriever:
    """로컬에 저장한 Chunk 벡터를 코사인 유사도로 검색한다.

    이 구현은 pgvector를 도입하기 전 검증용 저장소다. 검색 인터페이스는
    유지하므로, 이후 DB 기반 검색기로 교체할 수 있다.
    """

    def __init__(self, entries: list[tuple[RagChunk, list[float]]], client: ClovaEmbeddingClient) -> None:
        self._entries = entries
        self._client = client

    @classmethod
    def from_jsonl(cls, path: Path | str, client: ClovaEmbeddingClient) -> "EmbeddedJsonRagRetriever":
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"임베딩 파일이 없습니다: {path}. "
                "먼저 scripts/rag/build_embeddings.py를 완료하세요."
            )
        entries: list[tuple[RagChunk, list[float]]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            vector = data.pop("embedding")
            if not isinstance(vector, list) or not vector:
                raise ValueError("임베딩 저장 파일에 비어 있거나 잘못된 벡터가 있습니다.")
            entries.append((RagChunk.from_dict(data), [float(value) for value in vector]))
        if not entries:
            raise ValueError("임베딩 파일이 비어 있습니다. 임베딩 생성을 다시 실행하세요.")
        return cls(entries, client)

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            raise ValueError("질문 벡터와 문서 벡터의 차원이 다릅니다.")
        denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
        return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        allowed_product_ids: set[str] | None = None,
    ) -> list[RagChunk]:
        if not query.strip() or top_k < 1:
            return []
        if allowed_product_ids is not None and not allowed_product_ids:
            return []
        query_vector = self._client.embed(query)
        scored = [
            RagChunk(**{**chunk.__dict__, "score": self._cosine(query_vector, vector)})
            for chunk, vector in self._entries
            if allowed_product_ids is None or chunk.product_id in allowed_product_ids
        ]
        result: list[RagChunk] = []
        seen_sections: set[tuple[str, str, int | None]] = set()
        for chunk in sorted(scored, key=lambda item: item.score, reverse=True):
            section_key = (chunk.document_id, chunk.section_id, chunk.page_start)
            if section_key not in seen_sections:
                result.append(chunk)
                seen_sections.add(section_key)
            if len(result) == top_k:
                break
        return result

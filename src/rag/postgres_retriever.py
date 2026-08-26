"""PostgreSQL + pgvector를 검색하는 RAG Retriever."""

from __future__ import annotations

from typing import Any

from src.database.repository import PostgresPensionRepository
from src.observability import observe, update_observation

from .naver_embedding import ClovaEmbeddingClient
from .retriever import RagChunk


class PostgresRagRetriever:
    """질문을 임베딩한 뒤 `rag_chunks`에서 코사인 유사도 검색한다."""

    def __init__(
        self,
        repository: PostgresPensionRepository,
        client: ClovaEmbeddingClient,
        *,
        knowledge_type: str,
    ) -> None:
        if knowledge_type not in {"POLICY", "PRODUCT"}:
            raise ValueError("knowledge_type은 POLICY 또는 PRODUCT여야 합니다.")
        self._repository = repository
        self._client = client
        self._knowledge_type = knowledge_type

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        allowed_product_ids: set[str] | None = None,
    ) -> list[RagChunk]:
        if not query.strip() or top_k < 1:
            return []
        if self._knowledge_type == "PRODUCT" and allowed_product_ids is not None and not allowed_product_ids:
            return []
        allowed_ids = sorted(allowed_product_ids) if allowed_product_ids is not None else None
        with observe(
            f"{self._knowledge_type.lower()}-rag-retrieval",
            as_type="retriever",
            input={"query": query, "top_k": top_k, "allowed_product_ids": allowed_ids},
            metadata={"knowledge_type": self._knowledge_type, "store": "pgvector"},
        ) as retrieval:
            rows: list[dict[str, Any]] = self._repository.search_chunks(
                self._client.embed(query),
                knowledge_type=self._knowledge_type,
                top_k=top_k,
                allowed_product_ids=allowed_ids,
            )
            update_observation(
                retrieval,
                output={
                    "result_count": len(rows),
                    "chunks": [
                        {"chunk_id": row["chunk_id"], "document_id": row["document_id"], "score": row["score"]}
                        for row in rows
                    ],
                },
            )
        return [RagChunk.from_dict(row) for row in rows]

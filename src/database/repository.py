"""상품 필터와 pgvector 검색을 담당하는 PostgreSQL Repository."""

from __future__ import annotations

import json
from typing import Any


class PostgresPensionRepository:
    """한 PostgreSQL DB 안의 상품 테이블과 RAG 벡터 테이블을 다룬다."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @staticmethod
    def vector_literal(vector: list[float]) -> str:
        """pgvector 파라미터로 안전하게 전달할 텍스트 표현을 만든다."""
        if len(vector) != 1024:
            raise ValueError(f"CLOVA 임베딩은 1024차원이어야 합니다: {len(vector)}")
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def upsert_product(self, product: dict[str, Any]) -> None:
        self._connection.execute(
            """
            INSERT INTO pension_products (
                product_id, product_name, status, min_age, max_age, risk_level,
                allowed_employment, allowed_risk_preferences, goals, fee_rate,
                attributes, source_name
            ) VALUES (
                %(product_id)s, %(product_name)s, %(status)s, %(min_age)s, %(max_age)s, %(risk_level)s,
                %(allowed_employment)s, %(allowed_risk_preferences)s, %(goals)s, %(fee_rate)s,
                %(attributes)s::jsonb, %(source_name)s
            )
            ON CONFLICT (product_id) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                status = EXCLUDED.status,
                min_age = EXCLUDED.min_age,
                max_age = EXCLUDED.max_age,
                risk_level = EXCLUDED.risk_level,
                allowed_employment = EXCLUDED.allowed_employment,
                allowed_risk_preferences = EXCLUDED.allowed_risk_preferences,
                goals = EXCLUDED.goals,
                fee_rate = EXCLUDED.fee_rate,
                attributes = EXCLUDED.attributes,
                source_name = EXCLUDED.source_name,
                updated_at = NOW()
            """,
            {
                "product_id": product["product_id"],
                "product_name": product["product_name"],
                "status": product.get("status", "INACTIVE"),
                "min_age": product.get("min_age", 0),
                "max_age": product.get("max_age"),
                "risk_level": product.get("risk_level"),
                "allowed_employment": product.get("allowed_employment", []),
                "allowed_risk_preferences": product.get("allowed_risk_preferences", []),
                "goals": product.get("goals", []),
                "fee_rate": product.get("fee_rate"),
                "attributes": json.dumps(product.get("attributes", {}), ensure_ascii=False),
                "source_name": product.get("source_name"),
            },
        )

    def filter_products(self, user_conditions: dict[str, Any]) -> list[dict[str, Any]]:
        """추천 후보를 벡터 검색 전에 SQL 조건으로 정확히 줄인다."""
        rows = self._connection.execute(
            """
            SELECT product_id, product_name, status, min_age, max_age, risk_level,
                   allowed_employment, allowed_risk_preferences, goals, fee_rate, attributes
            FROM pension_products
            WHERE status = 'ACTIVE'
              AND min_age <= %(age)s
              AND (max_age IS NULL OR max_age >= %(age)s)
              AND %(employment_status)s = ANY(allowed_employment)
              AND %(risk_preference)s = ANY(allowed_risk_preferences)
              AND %(goal)s = ANY(goals)
            ORDER BY product_name
            """,
            {
                "age": user_conditions["age"],
                "employment_status": user_conditions["employment_status"],
                "risk_preference": user_conditions["risk_preference"],
                "goal": user_conditions["goal"],
            },
        ).fetchall()
        columns = (
            "product_id", "product_name", "status", "min_age", "max_age", "risk_level",
            "allowed_employment", "allowed_risk_preferences", "goals", "fee_rate", "attributes",
        )
        return [dict(zip(columns, row)) for row in rows]

    def upsert_chunk(self, record: dict[str, Any], *, knowledge_type: str) -> None:
        if knowledge_type not in {"POLICY", "PRODUCT"}:
            raise ValueError("knowledge_type은 POLICY 또는 PRODUCT여야 합니다.")
        if knowledge_type == "PRODUCT" and not record.get("product_id"):
            raise ValueError("상품 RAG Chunk에는 product_id가 필요합니다.")
        if knowledge_type == "POLICY" and record.get("product_id"):
            raise ValueError("규정 RAG Chunk에는 product_id를 넣지 않습니다.")
        embedding = self.vector_literal(record["embedding"])
        known_fields = {
            "chunk_id", "document_id", "document_title", "section_id", "section_title", "topic",
            "content", "page_start", "page_end", "validation_status", "product_id", "embedding", "score",
        }
        metadata = {key: value for key, value in record.items() if key not in known_fields}
        self._connection.execute(
            """
            INSERT INTO rag_chunks (
                chunk_id, knowledge_type, product_id, document_id, document_title,
                section_id, section_title, topic, content, page_start, page_end,
                validation_status, metadata, embedding
            ) VALUES (
                %(chunk_id)s, %(knowledge_type)s, %(product_id)s, %(document_id)s, %(document_title)s,
                %(section_id)s, %(section_title)s, %(topic)s, %(content)s, %(page_start)s, %(page_end)s,
                %(validation_status)s, %(metadata)s::jsonb, %(embedding)s::vector
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                knowledge_type = EXCLUDED.knowledge_type,
                product_id = EXCLUDED.product_id,
                document_id = EXCLUDED.document_id,
                document_title = EXCLUDED.document_title,
                section_id = EXCLUDED.section_id,
                section_title = EXCLUDED.section_title,
                topic = EXCLUDED.topic,
                content = EXCLUDED.content,
                page_start = EXCLUDED.page_start,
                page_end = EXCLUDED.page_end,
                validation_status = EXCLUDED.validation_status,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            {
                **record,
                "knowledge_type": knowledge_type,
                "product_id": record.get("product_id"),
                "validation_status": record.get("validation_status", "NEEDS_REVIEW"),
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "embedding": embedding,
            },
        )

    def search_chunks(
        self,
        query_embedding: list[float],
        *,
        knowledge_type: str,
        top_k: int = 3,
        allowed_product_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """코사인 거리로 RAG Chunk를 찾고, 상품 검색은 후보 ID로 먼저 제한한다."""
        if knowledge_type not in {"POLICY", "PRODUCT"}:
            raise ValueError("knowledge_type은 POLICY 또는 PRODUCT여야 합니다.")
        if top_k < 1 or (knowledge_type == "PRODUCT" and not allowed_product_ids):
            return []
        rows = self._connection.execute(
            """
            SELECT chunk_id, document_id, document_title, section_id, section_title, topic,
                   content, page_start, page_end, validation_status, product_id,
                   1 - (embedding <=> %(embedding)s::vector) AS score
            FROM rag_chunks
            WHERE knowledge_type = %(knowledge_type)s
              AND (
                  %(allowed_product_ids)s::text[] IS NULL
                  OR product_id = ANY(%(allowed_product_ids)s::text[])
              )
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(top_k)s
            """,
            {
                "embedding": self.vector_literal(query_embedding),
                "knowledge_type": knowledge_type,
                "allowed_product_ids": allowed_product_ids,
                "top_k": top_k,
            },
        ).fetchall()
        columns = (
            "chunk_id", "document_id", "document_title", "section_id", "section_title", "topic",
            "content", "page_start", "page_end", "validation_status", "product_id", "score",
        )
        return [dict(zip(columns, row)) for row in rows]

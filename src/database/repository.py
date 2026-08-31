"""상품 필터와 pgvector 검색을 담당하는 PostgreSQL Repository."""

from __future__ import annotations

import json
from typing import Any

from src.products.catalog import risk_grade_range


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

    def upsert_product_class(self, product_class: dict[str, Any]) -> None:
        """실제 가입 단위인 상품 클래스를 한 행으로 저장한다."""
        self._connection.execute(
            """
            INSERT INTO product_classes (
                class_id, class_name, product_id, product_name, risk_grade,
                asset_type, investment_region, eligible_account_types, sales_channel,
                capital_protection, redemption_available, redemption_fee_type,
                total_fee_rate, upfront_fee_rate, status, source_page
            ) VALUES (
                %(class_id)s, %(class_name)s, %(product_id)s, %(product_name)s, %(risk_grade)s,
                %(asset_type)s, %(investment_region)s, %(eligible_account_types)s, %(sales_channel)s,
                %(capital_protection)s, %(redemption_available)s, %(redemption_fee_type)s,
                %(total_fee_rate)s, %(upfront_fee_rate)s, %(status)s, %(source_page)s
            )
            ON CONFLICT (class_id) DO UPDATE SET
                class_name = EXCLUDED.class_name,
                product_id = EXCLUDED.product_id,
                product_name = EXCLUDED.product_name,
                risk_grade = EXCLUDED.risk_grade,
                asset_type = EXCLUDED.asset_type,
                investment_region = EXCLUDED.investment_region,
                eligible_account_types = EXCLUDED.eligible_account_types,
                sales_channel = EXCLUDED.sales_channel,
                capital_protection = EXCLUDED.capital_protection,
                redemption_available = EXCLUDED.redemption_available,
                redemption_fee_type = EXCLUDED.redemption_fee_type,
                total_fee_rate = EXCLUDED.total_fee_rate,
                upfront_fee_rate = EXCLUDED.upfront_fee_rate,
                status = EXCLUDED.status,
                source_page = EXCLUDED.source_page,
                updated_at = NOW()
            """,
            {
                "class_id": product_class["class_id"],
                "class_name": product_class["class_name"],
                "product_id": product_class["product_id"],
                "product_name": product_class["product_name"],
                "risk_grade": product_class.get("risk_grade"),
                "asset_type": product_class.get("asset_type", "OTHER"),
                "investment_region": product_class.get("investment_region", "UNKNOWN"),
                "eligible_account_types": product_class.get("eligible_account_types", []),
                "sales_channel": product_class.get("sales_channel", "UNKNOWN"),
                "capital_protection": product_class.get("capital_protection", "UNKNOWN"),
                "redemption_available": product_class.get("redemption_available", "UNKNOWN"),
                "redemption_fee_type": product_class.get("redemption_fee_type", "UNKNOWN"),
                "total_fee_rate": product_class.get("total_fee_rate"),
                "upfront_fee_rate": product_class.get("upfront_fee_rate"),
                "status": product_class.get("status", "UNKNOWN"),
                "source_page": product_class.get("source_page"),
            },
        )

    def filter_product_classes(self, user_conditions: dict[str, Any]) -> list[dict[str, Any]]:
        """계좌 유형·위험 선호·가입 채널로 가입 가능한 클래스 후보를 줄인다."""
        min_risk_grade, max_risk_grade = risk_grade_range(user_conditions["risk_preference"])
        rows = self._connection.execute(
            """
            SELECT class_id, class_name, product_id, product_name, risk_grade,
                   asset_type, investment_region, eligible_account_types, sales_channel,
                   capital_protection, redemption_available, redemption_fee_type,
                   total_fee_rate, upfront_fee_rate, status, source_page
            FROM product_classes
            WHERE status = 'ON_SALE'
              AND %(account_type)s = ANY(eligible_account_types)
              AND risk_grade BETWEEN %(min_risk_grade)s AND %(max_risk_grade)s
              AND (
                  %(sales_channel)s::text IS NULL
                  OR sales_channel = %(sales_channel)s::text
              )
            ORDER BY risk_grade DESC, total_fee_rate ASC NULLS LAST, product_name, class_name
            """,
            {
                "account_type": user_conditions["account_type"],
                "min_risk_grade": min_risk_grade,
                "max_risk_grade": max_risk_grade,
                "sales_channel": user_conditions.get("sales_channel"),
            },
        ).fetchall()
        columns = (
            "class_id", "class_name", "product_id", "product_name", "risk_grade",
            "asset_type", "investment_region", "eligible_account_types", "sales_channel",
            "capital_protection", "redemption_available", "redemption_fee_type",
            "total_fee_rate", "upfront_fee_rate", "status", "source_page",
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

    def delete_chunks_by_knowledge_type(self, knowledge_type: str) -> int:
        """지정 지식 유형의 청크만 삭제해 재색인을 준비한다."""
        if knowledge_type not in {"POLICY", "PRODUCT"}:
            raise ValueError("knowledge_type은 POLICY 또는 PRODUCT여야 합니다.")
        result = self._connection.execute(
            "DELETE FROM rag_chunks WHERE knowledge_type = %(knowledge_type)s",
            {"knowledge_type": knowledge_type},
        )
        return result.rowcount

    def search_chunks(
        self,
        query_embedding: list[float],
        *,
        knowledge_type: str,
        top_k: int = 5,
        allowed_product_ids: list[str] | None = None,
        per_product_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """코사인 거리로 RAG Chunk를 찾고, 상품 검색은 후보 ID로 먼저 제한한다."""
        if knowledge_type not in {"POLICY", "PRODUCT"}:
            raise ValueError("knowledge_type은 POLICY 또는 PRODUCT여야 합니다.")
        if (
            top_k < 1
            or (knowledge_type == "PRODUCT" and not allowed_product_ids)
            or (per_product_limit is not None and per_product_limit < 1)
        ):
            return []
        rows = self._connection.execute(
            """
            WITH ranked_chunks AS (
                SELECT chunk_id, document_id, document_title, section_id, section_title, topic,
                       content, page_start, page_end, validation_status, product_id,
                       1 - (embedding <=> %(embedding)s::vector) AS score,
                       ROW_NUMBER() OVER (
                           PARTITION BY product_id
                           ORDER BY embedding <=> %(embedding)s::vector
                       ) AS product_rank
                FROM rag_chunks
                WHERE knowledge_type = %(knowledge_type)s
                  AND (
                      %(allowed_product_ids)s::text[] IS NULL
                      OR product_id = ANY(%(allowed_product_ids)s::text[])
                  )
            )
            SELECT chunk_id, document_id, document_title, section_id, section_title, topic,
                   content, page_start, page_end, validation_status, product_id, score
            FROM ranked_chunks
            WHERE %(per_product_limit)s::integer IS NULL
               OR product_rank <= %(per_product_limit)s::integer
            ORDER BY score DESC
            LIMIT %(top_k)s
            """,
            {
                "embedding": self.vector_literal(query_embedding),
                "knowledge_type": knowledge_type,
                "allowed_product_ids": allowed_product_ids,
                "per_product_limit": per_product_limit,
                "top_k": top_k,
            },
        ).fetchall()
        columns = (
            "chunk_id", "document_id", "document_title", "section_id", "section_title", "topic",
            "content", "page_start", "page_end", "validation_status", "product_id", "score",
        )
        return [dict(zip(columns, row)) for row in rows]

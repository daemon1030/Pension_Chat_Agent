"""검증된 상품 전처리 JSON을 DB용 데이터와 Product RAG용 데이터로 분리한다."""

from __future__ import annotations

import re
from typing import Any


PENSION_ACCOUNT_MAPPING = {
    "PENSION_SAVINGS": ["PENSION_SAVINGS"],
    "IRP": ["IRP"],
    # 투자설명서의 퇴직연금 클래스는 일반적으로 퇴직연금과 IRP에서 모두 가입 가능하다.
    "RETIREMENT_PENSION": ["IRP", "RETIREMENT_PENSION"],
}


def _normalize_boolean(value: Any) -> str:
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    return value if value in {"TRUE", "FALSE", "UNKNOWN"} else "UNKNOWN"


def _normalize_fee(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def normalize_product_class(product_class: dict[str, Any]) -> dict[str, Any]:
    """전처리 단계의 단일 account_type을 DB 적재용 배열로 정규화한다."""
    account_type = product_class.get("account_type")
    sales_channel = product_class.get("sales_channel")
    return {
        "class_id": product_class["class_id"],
        "class_name": product_class["class_name"],
        "product_id": product_class["product_id"],
        "product_name": product_class["product_name"],
        "risk_grade": product_class.get("risk_grade"),
        "asset_type": product_class.get("asset_type", "OTHER"),
        "investment_region": product_class.get("investment_region", "UNKNOWN"),
        "eligible_account_types": PENSION_ACCOUNT_MAPPING.get(account_type, []),
        "sales_channel": "UNKNOWN" if sales_channel == "DIRECT" else sales_channel,
        "capital_protection": _normalize_boolean(product_class.get("capital_protection")),
        "redemption_available": _normalize_boolean(product_class.get("redemption_available")),
        "redemption_fee_type": product_class.get("redemption_fee_type", "UNKNOWN"),
        "total_fee_rate": _normalize_fee(product_class.get("total_fee_rate")),
        "upfront_fee_rate": _normalize_fee(product_class.get("upfront_fee_rate")),
        "status": product_class.get("status", "UNKNOWN"),
        "source_page": product_class.get("source_page"),
    }


def to_product_rag_document(document: dict[str, Any], source_name: str) -> dict[str, Any]:
    """전처리 RAG 청크를 기존 임베딩 로더가 읽는 rag_ready 형식으로 바꾼다."""
    product_id = document.get("product_id") or document["product_classes"][0]["product_id"]
    product_name = document.get("product_name") or document["product_classes"][0]["product_name"]
    document_id = f"PRODUCT_{product_id}"
    rag_data = []
    for index, chunk in enumerate(document["product_rag_chunks"], start=1):
        rag_data.append({
            "chunk_id": chunk["chunk_id"],
            "document_id": document_id,
            "document_title": product_name,
            "section_id": f"SEC_{index:03d}",
            "section_title": chunk["topic"],
            "topic": chunk["topic"],
            "content": chunk["content"],
            "page_start": chunk["page"],
            "page_end": chunk["page"],
            "validation_status": "NEEDS_REVIEW",
            "product_id": product_id,
            "effective_date": chunk.get("effective_date"),
        })
    return {
        "document_id": document_id,
        "document_title": product_name,
        "source_file": source_name,
        "rag_data": rag_data,
    }


def product_rag_filename(product_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", product_id)
    return f"DOC_PRODUCT_{safe_id}_rag_ready.json"

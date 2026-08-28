from src.products.preprocessing_split import normalize_product_class, to_product_rag_document


def test_normalizes_a_class_for_the_database():
    result = normalize_product_class({
        "class_id": "C001", "class_name": "C-퇴직e", "product_id": "P001", "product_name": "예시",
        "risk_grade": 6, "asset_type": "BOND", "investment_region": "DOMESTIC",
        "account_type": "RETIREMENT_PENSION", "sales_channel": "DIRECT",
        "capital_protection": False, "redemption_available": True, "redemption_fee_type": "NONE",
        "total_fee_rate": "UNKNOWN", "upfront_fee_rate": 0, "status": "ON_SALE",
    })

    assert result["eligible_account_types"] == ["IRP", "RETIREMENT_PENSION"]
    assert result["sales_channel"] == "UNKNOWN"
    assert result["capital_protection"] == "FALSE"
    assert result["total_fee_rate"] is None


def test_converts_product_chunks_to_rag_ready_document():
    result = to_product_rag_document({
        "product_id": "P001", "product_name": "예시", "product_classes": [],
        "product_rag_chunks": [{
            "chunk_id": "P001_RISK_01", "product_id": "P001", "product_name": "예시",
            "topic": "RISK", "content": "위험 설명", "page": 3, "effective_date": "2025-01-01",
        }],
    }, "source.json")

    assert result["document_id"] == "PRODUCT_P001"
    assert result["rag_data"][0]["page_start"] == 3
    assert result["rag_data"][0]["effective_date"] == "2025-01-01"

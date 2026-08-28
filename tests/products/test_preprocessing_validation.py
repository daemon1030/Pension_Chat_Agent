from src.products.preprocessing_validation import validate_product_document


def test_validates_missing_required_class_data(tmp_path):
    path = tmp_path / "product.json"
    path.write_text(
        """{
          "source_pdf": "sample.pdf",
          "product_id": "P001",
          "product_name": "예시 상품",
          "document_metadata": {},
          "product_classes": [{
            "class_id": "C001", "class_name": "C-P", "product_id": "P001", "product_name": "예시 상품",
            "risk_grade": null, "asset_type": "BOND", "investment_region": "DOMESTIC",
            "account_type": "PENSION_SAVINGS", "sales_channel": "ONLINE", "capital_protection": "FALSE",
            "redemption_available": "TRUE", "redemption_fee_type": "NONE", "total_fee_rate": 0.1,
            "upfront_fee_rate": 0, "status": "UNKNOWN"
          }],
          "product_rag_chunks": [{
            "chunk_id": "P001_OVERVIEW_01", "product_id": "P001", "product_name": "예시 상품",
            "topic": "OVERVIEW", "content": "상품 설명", "page": 1, "effective_date": "2025-01-01"
          }]
        }""",
        encoding="utf-8",
    )

    result = validate_product_document(path)

    assert any(issue["code"] == "EMPTY_CLASS_FIELD" and issue["path"].endswith("risk_grade") for issue in result["issues"])
    assert any(issue["code"] == "LEGACY_ACCOUNT_TYPE" for issue in result["issues"])
    assert any(issue["code"] == "UNKNOWN_SALE_STATUS" for issue in result["issues"])

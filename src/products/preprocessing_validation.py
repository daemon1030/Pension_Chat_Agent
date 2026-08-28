"""상품 투자설명서 전처리 JSON의 적재 가능 여부를 검사한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_REQUIRED_FIELDS = {
    "product_classes",
    "product_rag_chunks",
}

ROOT_RECOMMENDED_FIELDS = {"source_pdf", "product_id", "product_name", "document_metadata"}

CLASS_REQUIRED_FIELDS = {
    "class_id",
    "class_name",
    "product_id",
    "product_name",
    "risk_grade",
    "asset_type",
    "investment_region",
    "sales_channel",
    "capital_protection",
    "redemption_available",
    "redemption_fee_type",
    "status",
}

RAG_REQUIRED_FIELDS = {
    "chunk_id",
    "product_id",
    "product_name",
    "topic",
    "content",
    "page",
}

ASSET_TYPES = {"EQUITY", "BOND", "MIXED", "MMF", "ETF", "REIT", "DERIVATIVE", "OTHER"}
INVESTMENT_REGIONS = {"DOMESTIC", "OVERSEAS", "GLOBAL", "MIXED", "UNKNOWN"}
SALES_CHANNELS = {"ONLINE", "OFFLINE", "ONLINE_SUPER", "INSTITUTIONAL", "WRAP_TRUST", "UNKNOWN"}
CAPITAL_PROTECTIONS = {"TRUE", "FALSE", "UNKNOWN"}
REDEMPTION_AVAILABILITY = {"TRUE", "FALSE", "CONDITIONAL", "UNKNOWN"}
REDEMPTION_FEE_TYPES = {"NONE", "FIXED_RATE", "CONDITIONAL", "UNKNOWN"}
TARGET_STATUSES = {"ON_SALE", "SUSPENDED", "ENDED", "UNKNOWN"}
RAW_ACCOUNT_TYPES = {
    "PENSION_SAVINGS", "IRP", "RETIREMENT_PENSION", "NOT_ELIGIBLE", "GENERAL",
    "INSTITUTIONAL", "ASSET_MANAGER", "FUND_ONLY", "HIGH_NET_WORTH",
    "HOUSING_SAVINGS", "WRAP", "WRAP_TRUST",
}
RAG_TOPICS = {
    "OVERVIEW", "STRATEGY", "RISK", "LIQUIDITY", "FEE", "ACCOUNT_ELIGIBILITY", "SPECIAL_NOTICE",
}


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _issue(issues: list[dict[str, str]], severity: str, code: str, path: str, message: str) -> None:
    issues.append({"severity": severity, "code": code, "path": path, "message": message})


def _validate_choice(
    issues: list[dict[str, str]], value: Any, allowed: set[str], path: str, field: str
) -> None:
    if _present(value) and value not in allowed:
        _issue(issues, "ERROR", "INVALID_VALUE", path, f"{field} 값이 허용 범위에 없습니다: {value!r}")


def validate_product_document(path: Path) -> dict[str, Any]:
    """투자설명서 전처리 파일 한 개를 검사해 JSON 직렬화 가능한 결과를 반환한다."""
    issues: list[dict[str, str]] = []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _issue(issues, "ERROR", "INVALID_JSON", "$", str(error))
        return {"file": str(path), "class_count": 0, "rag_chunk_count": 0, "issues": issues}

    if not isinstance(document, dict):
        _issue(issues, "ERROR", "INVALID_ROOT", "$", "JSON 최상위 값은 객체여야 합니다.")
        return {"file": str(path), "class_count": 0, "rag_chunk_count": 0, "issues": issues}

    for field in sorted(ROOT_REQUIRED_FIELDS):
        if field not in document:
            _issue(issues, "ERROR", "MISSING_ROOT_FIELD", f"$.{field}", "필수 최상위 필드가 없습니다.")
        elif not _present(document[field]):
            _issue(issues, "ERROR", "EMPTY_ROOT_FIELD", f"$.{field}", "필수 최상위 필드 값이 비어 있습니다.")
    for field in sorted(ROOT_RECOMMENDED_FIELDS):
        if field not in document:
            _issue(
                issues, "WARNING", "MISSING_RECOMMENDED_ROOT_FIELD", f"$.{field}",
                "파일 추적과 병합을 위해 추가하는 것을 권장합니다.",
            )

    root_product_id = document.get("product_id")
    root_product_name = document.get("product_name")
    classes = document.get("product_classes")
    chunks = document.get("product_rag_chunks")
    if not isinstance(classes, list):
        _issue(issues, "ERROR", "INVALID_CLASS_LIST", "$.product_classes", "product_classes는 배열이어야 합니다.")
        classes = []
    if not isinstance(chunks, list):
        _issue(issues, "ERROR", "INVALID_RAG_LIST", "$.product_rag_chunks", "product_rag_chunks는 배열이어야 합니다.")
        chunks = []

    if not classes:
        _issue(issues, "ERROR", "EMPTY_CLASS_LIST", "$.product_classes", "최소 한 개의 상품 클래스가 필요합니다.")
    if not chunks:
        _issue(issues, "ERROR", "EMPTY_RAG_LIST", "$.product_rag_chunks", "최소 한 개의 Product RAG 청크가 필요합니다.")

    # 일부 전처리 파일은 최상위 상품 메타데이터 없이 클래스·RAG 배열만 가진다.
    # 이런 파일은 첫 클래스의 상품 식별자를 기준으로 내부 일관성을 검사한다.
    product_id = root_product_id or (classes[0].get("product_id") if classes and isinstance(classes[0], dict) else None)
    product_name = root_product_name or (classes[0].get("product_name") if classes and isinstance(classes[0], dict) else None)

    seen_class_ids: set[str] = set()
    for index, product_class in enumerate(classes):
        item_path = f"$.product_classes[{index}]"
        if not isinstance(product_class, dict):
            _issue(issues, "ERROR", "INVALID_CLASS", item_path, "클래스는 객체여야 합니다.")
            continue
        for field in sorted(CLASS_REQUIRED_FIELDS):
            if field not in product_class:
                _issue(issues, "ERROR", "MISSING_CLASS_FIELD", f"{item_path}.{field}", "필수 클래스 필드가 없습니다.")
            elif not _present(product_class[field]):
                _issue(issues, "ERROR", "EMPTY_CLASS_FIELD", f"{item_path}.{field}", "필수 클래스 필드 값이 비어 있습니다.")

        class_id = product_class.get("class_id")
        if _present(class_id):
            if class_id in seen_class_ids:
                _issue(issues, "ERROR", "DUPLICATE_CLASS_ID", f"{item_path}.class_id", "같은 파일 안에 중복 class_id가 있습니다.")
            seen_class_ids.add(class_id)

        account_type = product_class.get("account_type")
        eligible_accounts = product_class.get("eligible_account_types")
        if not _present(account_type) and not _present(eligible_accounts):
            _issue(issues, "ERROR", "MISSING_ACCOUNT_TYPE", item_path, "account_type 또는 eligible_account_types가 필요합니다.")
        if _present(account_type):
            _validate_choice(issues, account_type, RAW_ACCOUNT_TYPES, f"{item_path}.account_type", "account_type")
            _issue(
                issues, "WARNING", "LEGACY_ACCOUNT_TYPE", f"{item_path}.account_type",
                "적재 전 eligible_account_types 배열로 변환해야 합니다.",
            )
        if _present(eligible_accounts):
            if not isinstance(eligible_accounts, list) or not all(
                account in {"PENSION_SAVINGS", "IRP", "RETIREMENT_PENSION"} for account in eligible_accounts
            ):
                _issue(issues, "ERROR", "INVALID_ELIGIBLE_ACCOUNTS", f"{item_path}.eligible_account_types", "허용된 연금계좌 배열이 아닙니다.")

        _validate_choice(issues, product_class.get("asset_type"), ASSET_TYPES, item_path, "asset_type")
        _validate_choice(issues, product_class.get("investment_region"), INVESTMENT_REGIONS, item_path, "investment_region")
        sales_channel = product_class.get("sales_channel")
        if sales_channel == "DIRECT":
            _issue(issues, "WARNING", "LEGACY_SALES_CHANNEL", f"{item_path}.sales_channel", "DIRECT를 ONLINE·OFFLINE·UNKNOWN 중 하나로 정규화해야 합니다.")
        else:
            _validate_choice(issues, sales_channel, SALES_CHANNELS, item_path, "sales_channel")
        for field, allowed in (
            ("capital_protection", CAPITAL_PROTECTIONS),
            ("redemption_available", REDEMPTION_AVAILABILITY),
        ):
            value = product_class.get(field)
            if isinstance(value, bool):
                _issue(issues, "WARNING", "LEGACY_BOOLEAN", f"{item_path}.{field}", "TRUE·FALSE 문자열로 정규화해야 합니다.")
            else:
                _validate_choice(issues, value, allowed, item_path, field)
        _validate_choice(issues, product_class.get("redemption_fee_type"), REDEMPTION_FEE_TYPES, item_path, "redemption_fee_type")

        risk_grade = product_class.get("risk_grade")
        if _present(risk_grade) and (not isinstance(risk_grade, int) or isinstance(risk_grade, bool) or not 1 <= risk_grade <= 6):
            _issue(issues, "ERROR", "INVALID_RISK_GRADE", f"{item_path}.risk_grade", "risk_grade는 1~6 정수여야 합니다.")
        for field in ("total_fee_rate", "upfront_fee_rate"):
            value = product_class.get(field)
            if value is None:
                _issue(issues, "WARNING", "UNKNOWN_FEE_RATE", f"{item_path}.{field}", "수수료를 확인하지 못했습니다.")
                continue
            if value == "UNKNOWN":
                _issue(issues, "WARNING", "UNKNOWN_FEE_RATE", f"{item_path}.{field}", "수수료를 확인하지 못했습니다.")
                continue
            if _present(value) and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0):
                _issue(issues, "ERROR", "INVALID_FEE_RATE", f"{item_path}.{field}", "수수료는 0 이상 숫자여야 합니다.")

        status = product_class.get("status")
        if status not in TARGET_STATUSES:
            if status in {"ACTIVE", "INACTIVE"}:
                _issue(issues, "WARNING", "LEGACY_STATUS", f"{item_path}.status", "적재 전 ON_SALE·SUSPENDED·ENDED·UNKNOWN 중 하나로 변환해야 합니다.")
            elif _present(status):
                _issue(issues, "ERROR", "INVALID_STATUS", f"{item_path}.status", f"허용되지 않는 상태값입니다: {status!r}")
        if status == "UNKNOWN":
            _issue(issues, "WARNING", "UNKNOWN_SALE_STATUS", f"{item_path}.status", "UNKNOWN 클래스는 추천 DB 필터에서 제외됩니다.")

        if root_product_id and product_class.get("product_id") != product_id:
            _issue(issues, "ERROR", "PRODUCT_ID_MISMATCH", f"{item_path}.product_id", "최상위 product_id와 다릅니다.")
        if root_product_name and product_class.get("product_name") != product_name:
            _issue(issues, "ERROR", "PRODUCT_NAME_MISMATCH", f"{item_path}.product_name", "최상위 product_name과 다릅니다.")
        if "source_page" not in product_class:
            _issue(issues, "WARNING", "MISSING_SOURCE_PAGE", item_path, "추적을 위해 source_page를 추가하는 것을 권장합니다.")

    for index, chunk in enumerate(chunks):
        item_path = f"$.product_rag_chunks[{index}]"
        if not isinstance(chunk, dict):
            _issue(issues, "ERROR", "INVALID_RAG_CHUNK", item_path, "RAG 청크는 객체여야 합니다.")
            continue
        for field in sorted(RAG_REQUIRED_FIELDS):
            if field not in chunk:
                _issue(issues, "ERROR", "MISSING_RAG_FIELD", f"{item_path}.{field}", "필수 RAG 필드가 없습니다.")
            elif not _present(chunk[field]):
                _issue(issues, "ERROR", "EMPTY_RAG_FIELD", f"{item_path}.{field}", "필수 RAG 필드 값이 비어 있습니다.")
        _validate_choice(issues, chunk.get("topic"), RAG_TOPICS, item_path, "topic")
        page = chunk.get("page")
        if _present(page) and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            _issue(issues, "ERROR", "INVALID_PAGE", f"{item_path}.page", "page는 1 이상의 정수여야 합니다.")
        if product_id and chunk.get("product_id") != product_id:
            _issue(issues, "ERROR", "RAG_PRODUCT_ID_MISMATCH", f"{item_path}.product_id", "최상위 product_id와 다릅니다.")
        if product_name and chunk.get("product_name") != product_name:
            _issue(issues, "ERROR", "RAG_PRODUCT_NAME_MISMATCH", f"{item_path}.product_name", "최상위 product_name과 다릅니다.")

    return {
        "file": str(path),
        "product_id": product_id,
        "class_count": len(classes),
        "rag_chunk_count": len(chunks),
        "issues": issues,
    }


def validate_product_directory(directory: Path) -> dict[str, Any]:
    """폴더의 모든 JSON을 검사하고 오류·경고 수를 집계한다."""
    files = sorted(directory.glob("*.json"))
    results = [validate_product_document(path) for path in files]
    errors = sum(1 for result in results for issue in result["issues"] if issue["severity"] == "ERROR")
    warnings = sum(1 for result in results for issue in result["issues"] if issue["severity"] == "WARNING")
    return {
        "directory": str(directory),
        "file_count": len(results),
        "valid_file_count": sum(
            not any(issue["severity"] == "ERROR" for issue in result["issues"])
            for result in results
        ),
        "error_count": errors,
        "warning_count": warnings,
        "results": results,
    }

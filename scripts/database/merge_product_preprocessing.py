"""검증된 상품 전처리 JSON을 기존 DB·Product RAG 적재 파일에 안전하게 추가한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.products.preprocessing_split import (
    normalize_product_class,
    product_rag_filename,
    to_product_rag_document,
)
from src.products.preprocessing_validation import validate_product_directory


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_product_id(document: dict[str, Any]) -> str:
    return str(document.get("product_id") or document["product_classes"][0]["product_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="새 상품 전처리 데이터를 기존 DB·Product RAG 결과물에 추가")
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data" / "상품 전처리")
    parser.add_argument(
        "--db-output", type=Path,
        default=PROJECT_ROOT / "data" / "product_db_ready" / "product_classes.json",
    )
    parser.add_argument("--rag-output-dir", type=Path, default=PROJECT_ROOT / "data" / "product_rag_ready")
    parser.add_argument(
        "--report", type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "product_preprocessing_merge.json",
    )
    args = parser.parse_args()

    validation = validate_product_directory(args.input_dir)
    if validation["error_count"]:
        raise SystemExit(f"전처리 오류 {validation['error_count']}건이 있어 병합할 수 없습니다.")
    if not args.db_output.is_file():
        raise SystemExit(f"기존 DB용 파일을 찾을 수 없습니다: {args.db_output}")
    if not args.rag_output_dir.is_dir():
        raise SystemExit(f"기존 Product RAG 폴더를 찾을 수 없습니다: {args.rag_output_dir}")

    db_payload = _read_json(args.db_output)
    existing_classes = db_payload.get("product_classes")
    if not isinstance(existing_classes, list):
        raise SystemExit("기존 DB용 파일에 product_classes 배열이 없습니다.")
    existing_class_ids = {str(row["class_id"]) for row in existing_classes}
    existing_product_ids = {str(row["product_id"]) for row in existing_classes}

    new_classes: list[dict[str, Any]] = []
    new_rag_documents: list[dict[str, Any]] = []
    skipped_existing_products: list[str] = []

    for source_path in sorted(args.input_dir.glob("*.json")):
        document = _read_json(source_path)
        product_id = _source_product_id(document)
        if product_id in existing_product_ids:
            skipped_existing_products.append(product_id)
            continue

        normalized_classes = [normalize_product_class(row) for row in document["product_classes"]]
        duplicate_class_ids = [row["class_id"] for row in normalized_classes if row["class_id"] in existing_class_ids]
        if duplicate_class_ids:
            raise ValueError(
                f"새 상품 {product_id}에 기존 class_id가 포함되어 있습니다: {', '.join(duplicate_class_ids)}"
            )
        existing_class_ids.update(row["class_id"] for row in normalized_classes)
        existing_product_ids.add(product_id)
        new_classes.extend(normalized_classes)

        rag_document = to_product_rag_document(document, source_path.name)
        rag_path = args.rag_output_dir / product_rag_filename(product_id)
        if rag_path.exists():
            raise ValueError(f"새 상품 {product_id}의 RAG 파일이 이미 존재합니다: {rag_path.name}")
        new_rag_documents.append(rag_document)

    db_payload["product_classes"] = [*existing_classes, *new_classes]
    args.db_output.write_text(json.dumps(db_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for rag_document in new_rag_documents:
        product_id = rag_document["document_id"].removeprefix("PRODUCT_")
        output_path = args.rag_output_dir / product_rag_filename(product_id)
        output_path.write_text(json.dumps(rag_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "input_file_count": validation["file_count"],
        "validation_error_count": validation["error_count"],
        "validation_warning_count": validation["warning_count"],
        "added_product_count": len(new_rag_documents),
        "added_class_count": len(new_classes),
        "skipped_existing_product_count": len(skipped_existing_products),
        "skipped_existing_product_ids": sorted(skipped_existing_products),
        "db_product_count_after_merge": len(existing_product_ids),
        "db_class_count_after_merge": len(db_payload["product_classes"]),
        "added_rag_chunk_count": sum(len(document["rag_data"]) for document in new_rag_documents),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

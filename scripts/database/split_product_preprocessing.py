"""상품 전처리 JSON을 PostgreSQL DB용과 Product RAG용으로 분리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.products.preprocessing_split import (
    normalize_product_class,
    product_rag_filename,
    to_product_rag_document,
)
from src.products.preprocessing_validation import validate_product_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="상품 전처리 데이터를 DB용·Product RAG용으로 분리")
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data" / "상품 전처리")
    parser.add_argument("--db-output", type=Path, default=PROJECT_ROOT / "data" / "product_db_ready" / "product_classes.json")
    parser.add_argument("--rag-output-dir", type=Path, default=PROJECT_ROOT / "data" / "product_rag_ready_from_preprocessing")
    args = parser.parse_args()

    validation = validate_product_directory(args.input_dir)
    if validation["error_count"]:
        raise SystemExit(
            f"전처리 오류 {validation['error_count']}건이 있어 분리할 수 없습니다. "
            "validate_product_preprocessing.py 보고서를 먼저 확인하세요."
        )

    classes: list[dict] = []
    documents: dict[str, dict] = {}
    seen_class_ids: set[str] = set()
    seen_source_hashes: set[str] = set()
    skipped_duplicate_files: list[str] = []
    for source_path in sorted(args.input_dir.glob("*.json")):
        source_text = source_path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        if source_hash in seen_source_hashes:
            skipped_duplicate_files.append(source_path.name)
            continue
        seen_source_hashes.add(source_hash)
        document = json.loads(source_text)
        for product_class in document["product_classes"]:
            normalized = normalize_product_class(product_class)
            if normalized["class_id"] in seen_class_ids:
                raise ValueError(f"중복 class_id가 있습니다: {normalized['class_id']}")
            seen_class_ids.add(normalized["class_id"])
            classes.append(normalized)
        rag_document = to_product_rag_document(document, source_path.name)
        if rag_document["document_id"] in documents:
            raise ValueError(f"중복 product_id가 있습니다: {rag_document['document_id']}")
        documents[rag_document["document_id"]] = rag_document

    args.db_output.parent.mkdir(parents=True, exist_ok=True)
    args.db_output.write_text(
        json.dumps({"product_classes": classes}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.rag_output_dir.mkdir(parents=True, exist_ok=True)
    for document in documents.values():
        output_path = args.rag_output_dir / product_rag_filename(document["document_id"].removeprefix("PRODUCT_"))
        output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    chunk_count = sum(len(document["rag_data"]) for document in documents.values())
    print(
        f"분리 완료: 상품 클래스 {len(classes)}개 → {args.db_output}\n"
        f"Product RAG 문서 {len(documents)}개, 청크 {chunk_count}개 → {args.rag_output_dir}\n"
        f"완전히 동일한 중복 파일 {len(skipped_duplicate_files)}개는 한 번만 사용했습니다."
    )


if __name__ == "__main__":
    main()

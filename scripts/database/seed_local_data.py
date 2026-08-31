"""현재 JSONL 임베딩과 상품 JSON을 PostgreSQL에 적재한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import PostgresPensionRepository, connect_from_env


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="JSONL 임베딩과 상품 카탈로그를 PostgreSQL에 적재")
    parser.add_argument(
        "--policy",
        type=Path,
        default=PROJECT_ROOT / "data/embeddings/rag_embeddings.jsonl",
        help="규정 RAG 임베딩 JSONL 경로",
    )
    parser.add_argument(
        "--product",
        type=Path,
        default=PROJECT_ROOT / "data/embeddings/product_embeddings_from_preprocessing.jsonl",
        help="상품 RAG 임베딩 JSONL 경로",
    )
    parser.add_argument(
        "--products",
        type=Path,
        default=PROJECT_ROOT / "data/product_db_ready/product_classes.json",
        help="상품 필터링 DB용 클래스 JSON 경로",
    )
    parser.add_argument(
        "--replace-policy",
        action="store_true",
        help="기존 POLICY RAG 청크만 삭제한 뒤 --policy 파일을 다시 적재합니다. 상품 데이터는 변경하지 않습니다.",
    )
    args = parser.parse_args()

    input_paths = (args.policy,) if args.replace_policy else (args.policy, args.product, args.products)
    missing_paths = [path for path in input_paths if not path.is_file()]
    if missing_paths:
        missing = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in missing_paths)
        parser.error(f"적재할 파일을 찾을 수 없습니다: {missing}")

    policy_chunks = load_jsonl(args.policy)
    with connect_from_env() as connection:
        repository = PostgresPensionRepository(connection)
        if args.replace_policy:
            deleted_policy_chunks = repository.delete_chunks_by_knowledge_type("POLICY")
        else:
            deleted_policy_chunks = 0
            product_classes = json.loads(args.products.read_text(encoding="utf-8")).get("product_classes", [])
            product_chunks = load_jsonl(args.product)
            for product_class in product_classes:
                repository.upsert_product_class(product_class)
        for chunk in policy_chunks:
            repository.upsert_chunk(chunk, knowledge_type="POLICY")
        if not args.replace_policy:
            for chunk in product_chunks:
                repository.upsert_chunk(chunk, knowledge_type="PRODUCT")
    if args.replace_policy:
        print(f"정책 RAG 교체 완료: 기존 규정 Chunk {deleted_policy_chunks}개 삭제, 새 규정 Chunk {len(policy_chunks)}개 적재")
    else:
        print(f"적재 완료: 상품 클래스 {len(product_classes)}개, 규정 Chunk {len(policy_chunks)}개, 상품 Chunk {len(product_chunks)}개")


if __name__ == "__main__":
    main()

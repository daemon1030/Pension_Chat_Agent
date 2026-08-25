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
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "data/embeddings/rag_embeddings.jsonl")
    parser.add_argument("--product", type=Path, default=PROJECT_ROOT / "data/embeddings/product_embeddings.jsonl")
    parser.add_argument("--products", type=Path, default=PROJECT_ROOT / "data/products.json")
    args = parser.parse_args()

    products = json.loads(args.products.read_text(encoding="utf-8")).get("products", [])
    policy_chunks = load_jsonl(args.policy)
    product_chunks = load_jsonl(args.product)
    with connect_from_env() as connection:
        repository = PostgresPensionRepository(connection)
        for product in products:
            repository.upsert_product(product)
        for chunk in policy_chunks:
            repository.upsert_chunk(chunk, knowledge_type="POLICY")
        for chunk in product_chunks:
            repository.upsert_chunk(chunk, knowledge_type="PRODUCT")
    print(f"적재 완료: 상품 {len(products)}개, 규정 Chunk {len(policy_chunks)}개, 상품 Chunk {len(product_chunks)}개")


if __name__ == "__main__":
    main()

"""CLOVA 임베딩 검색을 사용하는 RAG 전용 LangGraph 실행기."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import create_embedding_rag_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="CLOVA 임베딩 기반 연금 RAG 검색")
    parser.add_argument("query", help="검색할 질문")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--embedding-path", type=Path, default=PROJECT_ROOT / "data/embeddings/rag_embeddings.jsonl")
    args = parser.parse_args()

    workflow = create_embedding_rag_workflow(args.embedding_path)
    print(json.dumps(workflow.invoke({"query": args.query, "top_k": args.top_k}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

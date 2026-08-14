"""RAG 전용 LangGraph를 터미널에서 실행한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import create_rag_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 전용 연금 문서 검색")
    parser.add_argument("query", help="검색할 질문")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    workflow = create_rag_workflow(PROJECT_ROOT / "data/rag_ready")
    result = workflow.invoke({"query": args.query, "top_k": args.top_k})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

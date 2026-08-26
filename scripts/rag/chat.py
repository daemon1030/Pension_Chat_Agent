"""네이버 임베딩 RAG와 CLOVA 최종 답변 생성을 실행한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import create_postgres_clova_rag_workflow
from src.observability import append_chat_log, flush, observe, update_observation


def main() -> None:
    parser = argparse.ArgumentParser(description="CLOVA 최종 답변을 포함한 연금 RAG")
    parser.add_argument("query", help="질문")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    workflow = create_postgres_clova_rag_workflow()
    try:
        with observe(
            "pension-rag-chat",
            as_type="agent",
            input={"query": args.query, "top_k": args.top_k},
            metadata={"entrypoint": "scripts/rag/chat.py"},
        ) as trace:
            try:
                result = workflow.invoke({"query": args.query, "top_k": args.top_k})
            except Exception as error:
                update_observation(trace, output={"status": "ERROR", "error": f"{type(error).__name__}: {error}"})
                raise
            update_observation(
                trace,
                output={
                    "status": result.get("status"),
                    "answer": result.get("answer"),
                    "sources": result.get("sources", []),
                },
            )
    except Exception as error:
        append_chat_log(query=args.query, error=error, source="scripts/rag/chat.py")
        raise
    finally:
        flush()
    append_chat_log(query=args.query, result=result, source="scripts/rag/chat.py")
    response = {key: result[key] for key in ("status", "answer", "missing_fields", "follow_up_question", "sources")}
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

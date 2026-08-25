"""대표 질문 묶음을 실제 챗봇에 보내고 응답을 JSONL로 기록한다."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import create_postgres_clova_rag_workflow


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="챗봇 평가 질문을 실행하고 응답을 JSONL로 저장")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data/evaluation/chat_test_queries.jsonl")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/evaluation/chat_test_results.jsonl")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    args = parser.parse_args()

    cases = load_cases(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workflow = create_postgres_clova_rag_workflow()

    with args.output.open("w", encoding="utf-8") as output:
        for index, case in enumerate(cases, 1):
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                result = workflow.invoke({"query": case["query"], "top_k": args.top_k})
                record = {
                    **case,
                    "started_at": started_at,
                    "status": result.get("status"),
                    "answer": result.get("answer"),
                    "missing_fields": result.get("missing_fields", []),
                    "follow_up_question": result.get("follow_up_question"),
                    "sources": result.get("sources", []),
                    "error": None,
                }
            except Exception as error:  # 평가 전체가 한 요청 실패로 멈추지 않도록 기록한다.
                record = {
                    **case,
                    "started_at": started_at,
                    "status": "ERROR",
                    "answer": None,
                    "missing_fields": [],
                    "follow_up_question": None,
                    "sources": [],
                    "error": f"{type(error).__name__}: {error}",
                }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(f"{index}/{len(cases)} {case['case_id']}: {record['status']}")
            if index < len(cases):
                time.sleep(args.delay_seconds)

    print(f"완료: {len(cases)}개 결과 → {args.output}")


if __name__ == "__main__":
    main()

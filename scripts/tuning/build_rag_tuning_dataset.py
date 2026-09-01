"""질문 분석 튜닝 데이터에서 RAG 답변 튜닝 JSONL을 생성한다.

입력의 QueryAnalysis Completion을 신뢰해 검색·후보 선정에 그대로 사용한다.
따라서 답변 학습용 Text의 질문 분석 블록과 질문 분석 학습 데이터가 어긋나지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import connect_from_env
from src.database.repository import PostgresPensionRepository
from src.graph.nodes import (
    build_grounded_context,
    check_recommendation_requirements,
    no_grounded_context,
    no_matching_product,
    recommendation_follow_up,
    retrieve_selected_sources,
    store_candidate_products,
)
from src.llm.prompts import INFORMATION_RAG_SYSTEM_PROMPT, RECOMMENDATION_RAG_SYSTEM_PROMPT
from src.rag.naver_embedding import ClovaEmbeddingClient, EmbeddingRateLimitError
from src.rag.postgres_retriever import PostgresRagRetriever


def load_rows(path: Path) -> list[dict[str, Any]]:
    """JSON 배열 또는 JSONL 형식의 질문 분석 데이터를 읽는다."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        value = json.loads(text)
        if not isinstance(value, list):
            raise ValueError("입력 JSON은 객체 배열이어야 합니다.")
        return value
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_review_json(path: Path, rows: list[dict[str, Any]]) -> None:
    """사람이 검토하기 쉬운 들여쓰기 JSON 배열을 함께 저장한다.

    실제 튜닝 JSONL의 Completion은 문자열이어야 하지만, 검토 파일에서는 객체로
    풀어 각 필드가 줄마다 보이게 한다.
    """
    review_rows = []
    for row in rows:
        review_row = dict(row)
        completion = row["Completion"]
        review_row["Completion"] = json.loads(completion) if isinstance(completion, str) else completion
        review_rows.append(review_row)
    path.write_text(json.dumps(review_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def answer_text(state: dict[str, Any]) -> str:
    """실제 답변 생성 노드와 같은 Text 형태를 만든다."""
    context, _ = build_grounded_context(state.get("retrieved_chunks", []))
    analysis_context = {
        "intent": state["intent"],
        "retrieval_sources": state["retrieval_sources"],
        "user_conditions": state["user_conditions"],
        "candidate_products": state.get("recommended_products", []),
    }
    return (
        f"[사용자 질문]\n{state['query']}\n\n"
        f"[질문 분석 및 후보 결과]\n"
        f"{json.dumps(analysis_context, ensure_ascii=False, default=str)}\n\n"
        f"[검색 근거]\n{context or '(검색 근거 없음)'}"
    )


def completion_template() -> str:
    """튜닝 담당자가 채울 RagAnswer Completion의 빈 구조를 반환한다."""
    return json.dumps(
        {
            "status": "",
            "answer": "",
            "missing_fields": [],
            "follow_up_question": None,
        },
        ensure_ascii=False,
    )


class CachedThrottledEmbeddingClient:
    """대량 튜닝 검색에서 임베딩 호출을 재사용하고 API 속도 제한을 지킨다."""

    def __init__(self, client: ClovaEmbeddingClient, cache_path: Path, *, delay_seconds: float) -> None:
        self._client = client
        self._cache_path = cache_path
        self._delay_seconds = delay_seconds
        self._next_request_at = 0.0
        self._cache = (
            json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
        )

    def embed(self, text: str) -> list[float]:
        if text in self._cache:
            return self._cache[text]
        for attempt in range(11):
            remaining = self._next_request_at - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            try:
                embedding = self._client.embed(text)
                self._next_request_at = time.monotonic() + self._delay_seconds
                self._cache[text] = embedding
                self._cache_path.write_text(
                    json.dumps(self._cache, ensure_ascii=False), encoding="utf-8"
                )
                return embedding
            except EmbeddingRateLimitError as error:
                if attempt == 10:
                    raise
                wait_seconds = error.retry_after_seconds or 15.0
                print(f"임베딩 요청 한도 도달: {wait_seconds:.0f}초 후 재시도합니다.", file=sys.stderr)
                self._next_request_at = time.monotonic() + wait_seconds
        raise RuntimeError("도달할 수 없는 코드입니다.")


def build_state(
    row: dict[str, Any],
    *,
    repository: PostgresPensionRepository,
    policy_retriever: PostgresRagRetriever,
    product_retriever: PostgresRagRetriever,
    top_k: int,
) -> dict[str, Any] | None:
    """질문 분석 Completion을 바탕으로 실제 DB/RAG 검색 결과를 구성한다."""
    analysis = json.loads(row["Completion"])
    if analysis.get("is_pension_related") is not True:
        return None
    question = row["Text"].removeprefix("[사용자 질문]\n").strip()
    state: dict[str, Any] = {
        "query": question,
        "intent": analysis["intent"],
        "retrieval_sources": analysis.get("retrieval_sources", []),
        "search_queries": analysis.get("search_queries", []),
        "user_conditions": analysis.get("user_conditions", {}),
        "top_k": top_k,
    }
    if state["intent"] != "PENSION_RECOMMENDATION":
        return {**state, **retrieve_selected_sources(state, policy_retriever, product_retriever)}

    missing = check_recommendation_requirements(state)
    if missing["missing_fields"]:
        return {**state, **missing, **recommendation_follow_up(missing)}

    candidates = repository.filter_product_classes(state["user_conditions"])
    state.update(store_candidate_products(candidates, state["user_conditions"]))
    if not state["candidate_product_ids"]:
        return {**state, **no_matching_product(state)}
    state.update(retrieve_selected_sources(state, policy_retriever, product_retriever))
    if not state.get("recommended_products"):
        return {**state, **no_grounded_context()}
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 답변 튜닝 JSONL 생성")
    parser.add_argument("--input", type=Path, required=True, help="질문 분석 튜닝 데이터(JSON 또는 JSONL)")
    parser.add_argument("--output-dir", type=Path, default=Path("tuning_data"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--min-c-id",
        type=int,
        default=None,
        help="이 값보다 큰 C_ID만 생성합니다.",
    )
    parser.add_argument(
        "--embedding-delay-seconds",
        type=float,
        default=0.6,
        help="캐시에 없는 임베딩 API 요청 사이의 최소 간격(기본 0.6초)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="검토·작성용 들여쓰기 JSON만 만들고 JSONL은 만들지 않습니다.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="기존 JSON 파일을 유지하고 새 C_ID 결과만 뒤에 추가합니다. --json-only와 함께 사용합니다.",
    )
    args = parser.parse_args()
    if args.append and not args.json_only:
        parser.error("--append는 --json-only와 함께 사용해야 합니다.")

    repository = PostgresPensionRepository(connect_from_env())
    embedding_client = CachedThrottledEmbeddingClient(
        ClovaEmbeddingClient.from_env(),
        args.output_dir / ".rag_tuning_embedding_cache.json",
        delay_seconds=max(0.0, args.embedding_delay_seconds),
    )
    policy_retriever = PostgresRagRetriever(repository, embedding_client, knowledge_type="POLICY")
    product_retriever = PostgresRagRetriever(repository, embedding_client, knowledge_type="PRODUCT")
    information_rows: list[dict[str, Any]] = []
    recommendation_rows: list[dict[str, Any]] = []

    try:
        for row in load_rows(args.input):
            if args.min_c_id is not None and row.get("C_ID", -1) <= args.min_c_id:
                continue
            state = build_state(
                row,
                repository=repository,
                policy_retriever=policy_retriever,
                product_retriever=product_retriever,
                top_k=args.top_k,
            )
            if state is None:
                continue
            is_recommendation = state["intent"] == "PENSION_RECOMMENDATION"
            system_prompt = (
                RECOMMENDATION_RAG_SYSTEM_PROMPT if is_recommendation else INFORMATION_RAG_SYSTEM_PROMPT
            )
            target = recommendation_rows if is_recommendation else information_rows
            target.append(
                {
                    "System_Prompt": system_prompt,
                    "C_ID": row.get("C_ID"),
                    "T_ID": row.get("T_ID", 0),
                    "Text": answer_text(state),
                    "Completion": completion_template(),
                }
            )
    finally:
        repository._connection.close()

    if args.json_only:
        information_json = args.output_dir / "information_answer_train.json"
        recommendation_json = args.output_dir / "recommendation_answer_train.json"
        if args.append:
            def load_existing(path: Path) -> list[dict[str, Any]]:
                if not path.is_file():
                    return []
                rows = json.loads(path.read_text(encoding="utf-8"))
                existing_ids = {row.get("C_ID") for row in rows}
                duplicate_ids = existing_ids & {row.get("C_ID") for row in information_rows + recommendation_rows}
                if duplicate_ids:
                    raise ValueError(f"기존 파일과 중복된 C_ID가 있습니다: {sorted(duplicate_ids)}")
                return rows

            information_rows = load_existing(information_json) + information_rows
            recommendation_rows = load_existing(recommendation_json) + recommendation_rows
        write_review_json(information_json, information_rows)
        write_review_json(recommendation_json, recommendation_rows)
        print(f"정보형 {len(information_rows)}개: {information_json}")
        print(f"추천형 {len(recommendation_rows)}개: {recommendation_json}")
        return

    information_jsonl = args.output_dir / "information_answer_train.jsonl"
    recommendation_jsonl = args.output_dir / "recommendation_answer_train.jsonl"
    write_jsonl(information_jsonl, information_rows)
    write_jsonl(recommendation_jsonl, recommendation_rows)
    write_review_json(args.output_dir / "information_answer_train_review.json", information_rows)
    write_review_json(args.output_dir / "recommendation_answer_train_review.json", recommendation_rows)
    print(f"정보형 {len(information_rows)}개: {information_jsonl}")
    print(f"추천형 {len(recommendation_rows)}개: {recommendation_jsonl}")


if __name__ == "__main__":
    main()

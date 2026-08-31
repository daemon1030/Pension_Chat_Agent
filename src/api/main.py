"""공개 HTTP 요청을 연금 RAG 워크플로에 연결한다."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.database import PostgresPensionRepository, connect_from_env
from src.graph.workflow import create_postgres_clova_rag_workflow
from src.observability import append_chat_log, flush


logger = logging.getLogger(__name__)

app = FastAPI(title="Pension RAG API", version="0.1.0")


class AnswerResponse(BaseModel):
    question_id: str
    question: str
    retrieved_context: list[dict[str, Any]]
    think_trace: str
    answer: str


def get_workflow() -> Generator[Any, None, None]:
    """요청별 DB 연결을 만들고, 응답이 끝나면 반드시 닫는다."""
    connection = connect_from_env()
    try:
        yield create_postgres_clova_rag_workflow(
            repository=PostgresPensionRepository(connection)
        )
    finally:
        connection.close()


@app.get("/health")
def health() -> dict[str, str]:
    """컨테이너가 HTTP 요청을 받을 수 있는지만 확인하는 liveness endpoint."""
    return {"status": "ok"}


def build_think_trace(result: dict[str, Any]) -> str:
    """내부 추론 대신 실제 분류·검색 결과만 한 줄로 요약한다."""
    if result.get("scope") == "OUT_OF_SCOPE":
        return "연금 범위 밖 질문으로 분류 → 답변 제한"

    intent_label = (
        "상품 추천 질문" if result.get("intent") == "PENSION_RECOMMENDATION" else "연금 정보 질문"
    )
    if result.get("status") == "NEED_MORE_INFO":
        return f"{intent_label}으로 분류 → 필요한 정보가 부족해 추가 정보 요청"
    if result.get("status") == "NO_MATCHING_PRODUCT":
        return "상품 추천 질문으로 분류 → 조건에 맞는 상품 후보를 찾지 못함"

    chunk_count = len(result.get("retrieved_chunks", []))
    if not chunk_count:
        return f"{intent_label}으로 분류 → 검색 근거를 찾지 못해 답변 제한"
    source_label = "·".join(result.get("retrieval_sources", [])) or "RAG"
    return f"{intent_label}으로 분류 → {source_label} 문서 {chunk_count}건 검색 → 근거 기반 답변 생성"


def build_retrieved_context(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """외부 응답에는 원문 대신 문서 ID와 페이지 출처만 반환한다."""
    context: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for chunk in chunks:
        source = (chunk.get("document_id"), chunk.get("page_start"))
        if source in seen:
            continue
        seen.add(source)
        context.append({"document_id": source[0], "page": source[1]})
    return context


@app.get("/answer", response_model=AnswerResponse)
def answer(
    question_id: Annotated[str, Query(min_length=1, max_length=128)],
    question: Annotated[str, Query(min_length=1, max_length=1000)],
    workflow: Annotated[Any, Depends(get_workflow)],
) -> AnswerResponse:
    """질문 ID와 질문을 받아 근거·출처가 포함된 연금 답변을 반환한다."""
    try:
        result = workflow.invoke({"query": question, "top_k": 5})
    except Exception as error:
        logger.exception("answer generation failed", extra={"question_id": question_id})
        append_chat_log(query=question, error=error, source="src.api.main")
        raise HTTPException(status_code=503, detail="현재 답변을 생성할 수 없습니다. 잠시 후 다시 시도하세요.") from error
    finally:
        flush()

    append_chat_log(query=question, result=result, source="src.api.main")
    return AnswerResponse(
        question_id=question_id,
        question=question,
        retrieved_context=build_retrieved_context(result.get("retrieved_chunks", [])),
        think_trace=build_think_trace(result),
        answer=result["answer"],
    )

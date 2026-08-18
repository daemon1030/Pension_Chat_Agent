"""
RAG 전용 LangGraph 노드.
각 단계가 실제로 하는 일을 모아 둔 파일
"""

from __future__ import annotations

from typing import Any

from src.llm.hyperclova import ClovaChatClient
from src.llm.prompts import RAG_SYSTEM_PROMPT
from src.rag.retriever import JsonRagRetriever

from .state import RagGraphState


PENSION_DOMAIN_TERMS = frozenset({
    "연금", "연금저축", "개인연금", "퇴직연금", "퇴직금", "퇴직소득", "퇴직급여",
    "irp", "개인형irp", "db형", "dc형", "세액공제", "소득공제", "중도인출",
    "연금수령", "연금개시", "노후", "은퇴", "금융소득", "연금계좌", "tdf",
})


def check_scope(state: RagGraphState) -> dict[str, str]:
    """서비스 주제와 무관한 일상 질문은 RAG·LLM 호출 전에 종료한다."""
    query = state.get("query", "").lower().replace(" ", "")
    return {"scope": "IN_SCOPE" if any(term in query for term in PENSION_DOMAIN_TERMS) else "OUT_OF_SCOPE"}


def scope_route(state: RagGraphState) -> str:
    """check_scope() 이후 라우팅 용도의 함수"""
    return "retrieve" if state.get("scope") == "IN_SCOPE" else "out_of_scope"


def out_of_scope_response(_: RagGraphState) -> dict[str, Any]:
    return {
        "status": "OUT_OF_SCOPE",
        "answer": "현재 서비스는 연금 관련 질문만 안내할 수 있습니다.",
        "missing_fields": [],
        "follow_up_question": "연금저축, IRP, 퇴직연금 등 연금관련 궁금한 내용을 알려주세요.",
        "sources": [],
    }


def retrieve(state: RagGraphState, retriever: JsonRagRetriever) -> dict[str, Any]:
    """질문과 가장 가까운 RAG Chunk만 검색한다."""
    top_k = int(state.get("top_k", 3))
    chunks = retriever.search(state.get("query", ""), top_k=top_k)
    return {"retrieved_chunks": [chunk.to_dict() for chunk in chunks]}


def grounded_response(state: RagGraphState) -> dict[str, Any]:
    """검색된 원문만 출력하고, 근거가 없으면 답변을 보류한다.

    LLM을 아직 연결하지 않았으므로 문장을 새로 해석하거나 요약하지 않는다.
    """
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return no_grounded_context()

    context, sources = build_grounded_context(chunks)
    return {"status": "ANSWER", "answer": "검색된 문서 근거입니다. 아래 원문 범위에서만 확인해 주세요.\n\n" + context, "sources": sources}


def build_grounded_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """모델에 전달할 근거 텍스트와 API 응답용 출처를 함께 만든다."""
    excerpts = []
    sources = []
    seen_sources: set[tuple[str, str, int | None]] = set()
    for chunk in chunks:
        page = chunk.get("page_start")
        title = chunk.get("section_title") or chunk.get("topic") or "관련 문서"
        excerpts.append(f"[{chunk['document_id']} p.{page} | {title}]\n{chunk['content']}")
        source_key = (chunk["document_id"], chunk["section_id"], page)
        if source_key not in seen_sources:
            sources.append({
                "document_id": chunk["document_id"],
                "document_title": chunk.get("document_title"),
                "section_id": chunk["section_id"],
                "page": page,
                "validation_status": chunk.get("validation_status"),
            })
            seen_sources.add(source_key)

    return "\n\n".join(excerpts), sources


def generate_clova_answer(state: RagGraphState, client: ClovaChatClient) -> dict[str, Any]:
    """검색 근거가 있을 때만 CLOVA에 최종 자연어 답변을 요청한다."""
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return no_grounded_context()
    context, sources = build_grounded_context(chunks)
    user_prompt = f"[사용자 질문]\n{state.get('query', '')}\n\n[검색 근거]\n{context}\n"
    response = client.generate_rag_answer(system_prompt=RAG_SYSTEM_PROMPT, user_prompt=user_prompt)
    return {
        "status": response.status,
        "answer": response.answer,
        "missing_fields": response.missing_fields,
        "follow_up_question": response.follow_up_question,
        "sources": sources,
    }


def no_grounded_context() -> dict[str, Any]:
    return {"status": "NO_GROUNDED_CONTEXT", "answer": "제공된 문서에서 질문과 직접 연결되는 근거를 찾지 못했습니다. 확인 가능한 조건이나 문서 범위를 알려주세요.", "missing_fields": [], "follow_up_question": "어떤 연금 제도나 상황을 확인하고 싶은지 조금 더 구체적으로 알려주세요.", "sources": []}

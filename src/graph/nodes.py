"""
RAG 전용 LangGraph 노드.
각 단계가 실제로 하는 일을 모아 둔 파일
"""

from __future__ import annotations

import json
from typing import Any

from src.llm.hyperclova import ClovaChatClient
from src.llm.prompts import (
    INFORMATION_RAG_SYSTEM_PROMPT,
    QUERY_ANALYSIS_SYSTEM_PROMPT,
    RECOMMENDATION_RAG_SYSTEM_PROMPT,
)
from src.observability import observe, update_observation
from src.products.catalog import enrich_candidate_classes, missing_recommendation_fields

from .state import RagGraphState


PENSION_DOMAIN_TERMS = frozenset({
    "연금", "연금저축", "개인연금", "퇴직연금", "퇴직금", "퇴직소득", "퇴직급여", "irp", "개인형irp", "db형", "dc형", "세액공제", "소득공제", "중도인출", "연금수령",
    "연금개시", "노후", "은퇴", "금융소득", "연금계좌", "tdf", "펀드", "주식형", "채권형", "혼합형", "총보수", "수수료", "클래스", "수익률",
    "납입", "해지", "계좌이전", "연금소득세", "기타소득세", "과세이연", "절세", "연말정산", "위험자산", "위험성향", "원금보장", "장기투자", "포트폴리오", "투자설명서"
})

MAX_DB_CANDIDATE_PRODUCTS = 20
MAX_RECOMMENDED_PRODUCTS = 5
MAX_EVIDENCE_CHUNKS_PER_PRODUCT = 2


def check_scope(state: RagGraphState) -> dict[str, str]:
    """서비스 주제와 무관한 일상 질문은 RAG·LLM 호출 전에 종료한다."""
    query = state.get("query", "").lower().replace(" ", "")
    return {"scope": "IN_SCOPE" if any(term in query for term in PENSION_DOMAIN_TERMS) else "OUT_OF_SCOPE"}


def scope_route(state: RagGraphState) -> str:
    """check_scope() 이후 라우팅 용도의 함수"""
    return "analyze_query" if state.get("scope") == "IN_SCOPE" else "out_of_scope"


def out_of_scope_response(_: RagGraphState) -> dict[str, Any]:
    return {
        "status": "OUT_OF_SCOPE",
        "answer": "현재 서비스는 연금 관련 질문만 안내할 수 있습니다.",
        "missing_fields": [],
        "follow_up_question": "연금저축, IRP, 퇴직연금 등 연금관련 궁금한 내용을 알려주세요.",
        "sources": [],
    }


def analyze_query(state: RagGraphState, client: ClovaChatClient) -> dict[str, Any]:
    """첫 LLM 호출로 질문 유형과 사용자가 직접 밝힌 조건만 추출한다."""
    user_prompt = f"[사용자 질문]\n{state.get('query', '')}\n"
    with observe(
        "query-analysis",
        as_type="generation",
        input={"query": state.get("query", "")},
        metadata={"model_provider": "hyperclova"},
    ) as generation:
        analysis = client.generate_query_analysis(
            system_prompt=QUERY_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        update_observation(generation, output=analysis.model_dump(mode="json"))
    return {
        "is_pension_related": analysis.is_pension_related,
        "scope": "IN_SCOPE" if analysis.is_pension_related else "OUT_OF_SCOPE",
        "intent": analysis.intent,
        "retrieval_sources": analysis.retrieval_sources,
        "user_conditions": analysis.user_conditions.model_dump(
            exclude_none=True, exclude_defaults=True
        ),
    }


def analysis_scope_route(state: RagGraphState) -> str:
    """LLM의 2차 연금 관련성 판정 후 종료 또는 검색 경로를 고른다."""
    if not state.get("is_pension_related"):
        return "out_of_scope"
    return intent_route(state)


def intent_route(state: RagGraphState) -> str:
    """연금 설명 질문과 개인화 추천 질문을 서로 다른 검색 경로로 보낸다."""
    return "recommendation" if state.get("intent") == "PENSION_RECOMMENDATION" else "information"


def check_recommendation_requirements(state: RagGraphState) -> dict[str, Any]:
    """상품을 좁히기 전, 데모 정책의 필수 조건이 모두 있는지 확인한다."""
    return {"missing_fields": missing_recommendation_fields(state.get("user_conditions", {}))}


def recommendation_requirement_route(state: RagGraphState) -> str:
    return "need_more_info" if state.get("missing_fields") else "filter_products"


def recommendation_follow_up(state: RagGraphState) -> dict[str, Any]:
    missing_fields = state.get("missing_fields", [])
    return {
        "status": "NEED_MORE_INFO",
        "answer": "상품 후보를 확인하려면 계좌 유형과 투자 위험 선호가 필요합니다.",
        "missing_fields": missing_fields,
        "follow_up_question": (
            "어느 계좌에서 운용할 예정인지와 "
            "안정성·수익성 중 선호하는 방향을 알려주세요."
        ),
        "sources": [],
    }


def store_candidate_products(
    candidates: list[dict[str, Any]], user_conditions: dict[str, Any]
) -> dict[str, Any]:
    """클래스 후보와 Product RAG 필터용 고유 상품 ID를 State에 저장한다."""
    enriched_candidates = enrich_candidate_classes(candidates, user_conditions)
    # DB 결과는 클래스 단위일 수 있다. 추천 검색 대상은 같은 상품을 중복시키지
    # 않고, 먼저 등장한 20개의 고유 상품으로 제한한다.
    candidate_product_ids = list(dict.fromkeys(
        str(product["product_id"]) for product in enriched_candidates
    ))[:MAX_DB_CANDIDATE_PRODUCTS]
    return {
        "candidate_product_ids": candidate_product_ids,
        "candidate_products": [
            product for product in enriched_candidates
            if str(product["product_id"]) in candidate_product_ids
        ],
    }


def candidate_product_route(state: RagGraphState) -> str:
    return "retrieve_sources" if state.get("candidate_product_ids") else "no_matching_product"


def no_matching_product(_: RagGraphState) -> dict[str, Any]:
    return {
        "status": "NO_MATCHING_PRODUCT",
        "answer": "현재 등록된 상품 조건에서 일치하는 후보를 찾지 못했습니다.",
        "missing_fields": [],
        "follow_up_question": "다른 위험 선호나 연금 준비 목적도 함께 알려주시면 다시 확인할 수 있습니다.",
        "sources": [],
    }


def retrieve_selected_sources(
    state: RagGraphState,
    policy_retriever: Any,
    product_retriever: Any,
) -> dict[str, Any]:
    """첫 LLM이 선택한 Policy/Product RAG에서 근거를 모은다."""
    top_k = int(state.get("top_k", 3))
    selected = set(state.get("retrieval_sources", []))
    policy_chunks = []
    product_chunks = []
    if "POLICY_RAG" in selected:
        policy_chunks = policy_retriever.search(state.get("query", ""), top_k=top_k)
    is_recommendation = state.get("intent") == "PENSION_RECOMMENDATION"
    if "PRODUCT_RAG" in selected or is_recommendation:
        candidate_ids = state.get("candidate_product_ids", [])
        allowed_product_ids = set(candidate_ids) if candidate_ids else None
        if is_recommendation:
            product_chunks = product_retriever.search(
                state.get("query", ""),
                top_k=len(candidate_ids) * MAX_EVIDENCE_CHUNKS_PER_PRODUCT,
                allowed_product_ids=allowed_product_ids,
                per_product_limit=MAX_EVIDENCE_CHUNKS_PER_PRODUCT,
            )
        else:
            product_chunks = product_retriever.search(
                state.get("query", ""), top_k=top_k, allowed_product_ids=allowed_product_ids
            )

    if is_recommendation:
        recommended_products, evidence_chunks = rank_recommended_products(
            state.get("candidate_products", []), product_chunks
        )
        return {
            "recommended_products": recommended_products,
            "retrieved_chunks": [chunk.to_dict() for chunk in policy_chunks + evidence_chunks],
        }

    result = []
    seen_chunk_ids: set[str] = set()
    for chunk in sorted(policy_chunks + product_chunks, key=lambda item: item.score, reverse=True):
        if chunk.chunk_id not in seen_chunk_ids:
            result.append(chunk)
            seen_chunk_ids.add(chunk.chunk_id)
        if len(result) == top_k:
            break
    return {"retrieved_chunks": [chunk.to_dict() for chunk in result]}


def rank_recommended_products(
    candidates: list[dict[str, Any]], chunks: list[Any]
) -> tuple[list[dict[str, Any]], list[Any]]:
    """상품별 상위 근거 1~2개로 점수화하고 중복 없는 추천 목록을 만든다."""
    candidates_by_product: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        candidates_by_product.setdefault(str(candidate["product_id"]), []).append(candidate)

    evidence_by_product: dict[str, list[Any]] = {}
    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        product_id = chunk.product_id
        if product_id not in candidates_by_product:
            continue
        evidence = evidence_by_product.setdefault(product_id, [])
        if len(evidence) < MAX_EVIDENCE_CHUNKS_PER_PRODUCT:
            evidence.append(chunk)

    ranked: list[tuple[float, dict[str, Any], list[Any]]] = []
    for product_id, evidence in evidence_by_product.items():
        # 첫 근거가 핵심이고, 두 번째 근거는 보조 신호만 제공한다.
        score = evidence[0].score + sum(chunk.score for chunk in evidence[1:]) * 0.2
        representative = dict(candidates_by_product[product_id][0])
        representative["evidence_score"] = score
        representative["supporting_chunk_ids"] = [chunk.chunk_id for chunk in evidence]
        ranked.append((score, representative, evidence))

    ranked.sort(key=lambda item: item[0], reverse=True)
    # 근거가 3개 미만이어도 억지로 채우지 않는다. 최대 5개만 제시한다.
    selected = ranked[:MAX_RECOMMENDED_PRODUCTS]
    return (
        [product for _, product, _ in selected],
        [chunk for _, _, evidence in selected for chunk in evidence],
    )


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
    if state.get("intent") == "PENSION_RECOMMENDATION" and not state.get("recommended_products", []):
        return no_grounded_context()
    if not chunks:
        return no_grounded_context()
    context, sources = build_grounded_context(chunks)
    system_prompt = (
        RECOMMENDATION_RAG_SYSTEM_PROMPT
        if state.get("intent") == "PENSION_RECOMMENDATION"
        else INFORMATION_RAG_SYSTEM_PROMPT
    )
    user_conditions = {
        key: value
        for key, value in state.get("user_conditions", {}).items()
        if value is not None and value != "" and value != []
    }
    analysis_context = json.dumps(
        {
            "intent": state.get("intent"),
            "retrieval_sources": state.get("retrieval_sources", []),
            "user_conditions": user_conditions,
            "candidate_products": (
                state.get("recommended_products", [])
                if state.get("intent") == "PENSION_RECOMMENDATION"
                else state.get("candidate_products", [])
            ),
        },
        ensure_ascii=False,
        default=str,
    )
    user_prompt = (
        f"[사용자 질문]\n{state.get('query', '')}\n\n"
        f"[질문 분석 및 후보 결과]\n{analysis_context}\n\n"
        f"[검색 근거]\n{context}\n"
    )
    with observe(
        "answer-generation",
        as_type="generation",
        input={"system_prompt": system_prompt, "user_prompt": user_prompt},
        metadata={"model_provider": "hyperclova"},
    ) as generation:
        response = client.generate_rag_answer(system_prompt=system_prompt, user_prompt=user_prompt)
        update_observation(generation, output=response.model_dump(mode="json"))
    return {
        "answer_generation_prompt": user_prompt,
        "status": response.status,
        "answer": response.answer,
        "missing_fields": response.missing_fields,
        "follow_up_question": response.follow_up_question,
        "sources": sources,
    }


def no_grounded_context() -> dict[str, Any]:
    return {"status": "NO_GROUNDED_CONTEXT", "answer": "제공된 문서에서 질문과 직접 연결되는 근거를 찾지 못했습니다. 확인 가능한 조건이나 문서 범위를 알려주세요.", "missing_fields": [], "follow_up_question": "어떤 연금 제도나 상황을 확인하고 싶은지 조금 더 구체적으로 알려주세요.", "sources": []}

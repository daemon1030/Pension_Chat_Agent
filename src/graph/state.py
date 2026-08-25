"""
RAG 이외 추가로 필요한 LangGraph State 정의.

사용자의 질문, 가져올 문서 수, 연금 관련 질문인지, 이번 질문에서 검색된 문서 조각, AI한테 제공할 근거 텍스트,
최종 답변, 추가로 필요한 정보, 사용자에게 할 추가 정보, 답변에 사용할 문서 출처, 처리 결과
"""

from typing import Any, Literal, TypedDict


class RagGraphState(TypedDict, total=False):
    """정형 DB·Rule Engine을 포함하지 않는 최소 상태."""

    query: str
    top_k: int

    # 싱글 턴에서만 쓰고 응답 후 저장하지 않는 사용자 분석 결과.
    is_pension_related: bool
    intent: Literal["PENSION_RECOMMENDATION", "PENSION_INFO"] | None
    user_conditions: dict[str, Any]
    candidate_product_ids: list[str]
    candidate_products: list[dict[str, Any]]

    scope: Literal["IN_SCOPE", "OUT_OF_SCOPE"]
    retrieved_chunks: list[dict]
    grounded_context: str
    # RAG 근거와 질문을 조합해 최종 답변 LLM에 전달한 사용자 메시지.
    answer_generation_prompt: str
    answer: str
    missing_fields: list[str]
    follow_up_question: str | None
    sources: list[dict]
    status: Literal["ANSWER", "NEED_MORE_INFO", "NO_GROUNDED_CONTEXT", "NO_MATCHING_PRODUCT", "OUT_OF_SCOPE"]

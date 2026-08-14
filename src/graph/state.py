"""RAG 전용 LangGraph State 정의."""

from typing import Literal, TypedDict


class RagGraphState(TypedDict, total=False):
    """정형 DB·Rule Engine을 포함하지 않는 최소 상태."""

    query: str
    top_k: int
    scope: Literal["IN_SCOPE", "OUT_OF_SCOPE"]
    retrieved_chunks: list[dict]
    grounded_context: str
    answer: str
    missing_fields: list[str]
    follow_up_question: str | None
    sources: list[dict]
    status: Literal["ANSWER", "NEED_MORE_INFO", "NO_GROUNDED_CONTEXT", "OUT_OF_SCOPE"]

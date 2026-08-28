"""RAG만 사용하는 최소 LangGraph 워크플로."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from src.rag.naver_embedding import ClovaEmbeddingClient
from src.rag.postgres_retriever import PostgresRagRetriever
from src.database.connection import connect_from_env
from src.database.repository import PostgresPensionRepository
from src.llm.hyperclova import ClovaChatClient
from src.observability import observe, update_observation

from .nodes import (
    analysis_scope_route,
    analyze_query,
    candidate_product_route,
    check_recommendation_requirements,
    check_scope,
    generate_clova_answer,
    no_matching_product,
    out_of_scope_response,
    recommendation_follow_up,
    recommendation_requirement_route,
    retrieve_selected_sources,
    scope_route,
    store_candidate_products,
)
from .state import RagGraphState


def create_postgres_clova_rag_workflow(
    embedding_client: ClovaEmbeddingClient | None = None,
    chat_client: ClovaChatClient | None = None,
    repository: PostgresPensionRepository | None = None,
):
    """PostgreSQL의 상품 조건과 pgvector RAG를 사용하는 챗봇 워크플로를 만든다."""
    database_repository = repository or PostgresPensionRepository(connect_from_env())
    client_for_embedding = embedding_client or ClovaEmbeddingClient.from_env()
    policy_retriever = PostgresRagRetriever(
        database_repository, client_for_embedding, knowledge_type="POLICY"
    )
    product_retriever = PostgresRagRetriever(
        database_repository, client_for_embedding, knowledge_type="PRODUCT"
    )
    client = chat_client or ClovaChatClient.from_env()
    def select_candidates(state: RagGraphState) -> dict[str, Any]:
        user_conditions = state.get("user_conditions", {})
        with observe(
            "product-db-filter",
            as_type="tool",
            input={"user_conditions": user_conditions},
            metadata={"store": "postgresql"},
        ) as database_filter:
            candidates = database_repository.filter_product_classes(user_conditions)
            update_observation(
                database_filter,
                output={
                    "candidate_count": len(candidates),
                    "candidate_product_ids": [product["product_id"] for product in candidates],
                },
            )
        return store_candidate_products(candidates, user_conditions)

    return _compile_clova_rag_workflow(
        policy_retriever=policy_retriever,
        product_retriever=product_retriever,
        select_candidates=select_candidates,
        chat_client=client,
    )


def _compile_clova_rag_workflow(
    *,
    policy_retriever: Any,
    product_retriever: Any,
    select_candidates: Callable[[RagGraphState], dict[str, Any]],
    chat_client: ClovaChatClient,
):
    """저장소와 무관한 공통 질문 분석·추천·답변 그래프를 컴파일한다."""
    graph = StateGraph(RagGraphState)
    graph.add_node("check_scope", check_scope)
    graph.add_node("out_of_scope", out_of_scope_response)
    graph.add_node("analyze_query", lambda state: analyze_query(state, chat_client))
    graph.add_node("check_recommendation_requirements", check_recommendation_requirements)
    graph.add_node("need_more_info", recommendation_follow_up)
    graph.add_node("filter_candidate_products", select_candidates)
    graph.add_node(
        "retrieve_sources",
        lambda state: retrieve_selected_sources(state, policy_retriever, product_retriever),
    )
    graph.add_node("no_matching_product", no_matching_product)
    graph.add_node("generate_answer", lambda state: generate_clova_answer(state, chat_client))
    graph.add_edge(START, "check_scope")
    graph.add_conditional_edges(
        "check_scope",
        scope_route,
        {"analyze_query": "analyze_query", "out_of_scope": "out_of_scope"},
    )
    graph.add_edge("out_of_scope", END)
    graph.add_conditional_edges(
        "analyze_query",
        analysis_scope_route,
        {
            "out_of_scope": "out_of_scope",
            "information": "retrieve_sources",
            "recommendation": "check_recommendation_requirements",
        },
    )
    graph.add_conditional_edges(
        "check_recommendation_requirements",
        recommendation_requirement_route,
        {"need_more_info": "need_more_info", "filter_products": "filter_candidate_products"},
    )
    graph.add_conditional_edges(
        "filter_candidate_products",
        candidate_product_route,
        {"retrieve_sources": "retrieve_sources", "no_matching_product": "no_matching_product"},
    )
    graph.add_edge("need_more_info", END)
    graph.add_edge("no_matching_product", END)
    graph.add_edge("retrieve_sources", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()

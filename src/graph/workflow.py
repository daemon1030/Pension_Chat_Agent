"""RAG만 사용하는 최소 LangGraph 워크플로."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from src.rag.retriever import JsonRagRetriever
from src.rag.naver_embedding import ClovaEmbeddingClient
from src.rag.postgres_retriever import PostgresRagRetriever
from src.rag.vector_retriever import EmbeddedJsonRagRetriever
from src.database.connection import connect_from_env
from src.database.repository import PostgresPensionRepository
from src.llm.hyperclova import ClovaChatClient
from src.products.catalog import load_products

from .nodes import (
    analyze_query,
    candidate_product_route,
    check_recommendation_requirements,
    check_scope,
    filter_candidate_products,
    generate_clova_answer,
    grounded_response,
    intent_route,
    no_matching_product,
    out_of_scope_response,
    recommendation_follow_up,
    recommendation_requirement_route,
    retrieve,
    scope_route,
    store_candidate_products,
)
from .state import RagGraphState


def create_rag_workflow(rag_directory: Path | str = "data/rag_ready"):

    retriever = JsonRagRetriever.from_directory(rag_directory)
    graph = StateGraph(RagGraphState)
    graph.add_node("retrieve", lambda state: retrieve(state, retriever))
    graph.add_node("grounded_response", grounded_response)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grounded_response")
    graph.add_edge("grounded_response", END)
    return graph.compile()


def create_embedding_rag_workflow(
    embedding_path: Path | str = "data/embeddings/rag_embeddings.jsonl",
    client: ClovaEmbeddingClient | None = None,
):
    """사용자 질문이 들어오면 질문을 임베딩하고, 
    RAG 저장소에서 의미적으로 가장 유사한 문서 청크 3개를 가져오는 
    컴파일된 LangGraph를 만든다."""
    retriever = EmbeddedJsonRagRetriever.from_jsonl(
        embedding_path, client or ClovaEmbeddingClient.from_env()
    )
    graph = StateGraph(RagGraphState)
    graph.add_node("retrieve", lambda state: retrieve(state, retriever))
    graph.add_node("grounded_response", grounded_response)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grounded_response")
    graph.add_edge("grounded_response", END)
    return graph.compile()


def create_clova_rag_workflow(
    embedding_path: Path | str = "data/embeddings/rag_embeddings.jsonl",
    embedding_client: ClovaEmbeddingClient | None = None,
    chat_client: ClovaChatClient | None = None,
    product_embedding_path: Path | str = "data/embeddings/product_embeddings.jsonl",
    product_catalog_path: Path | str = "data/products.json",
):
    """질문 유형에 따라 규정 RAG 또는 조건 필터된 상품 RAG를 연결한다."""
    client_for_embedding = embedding_client or ClovaEmbeddingClient.from_env()
    policy_retriever = EmbeddedJsonRagRetriever.from_jsonl(embedding_path, client_for_embedding)
    product_retriever = EmbeddedJsonRagRetriever.from_jsonl(product_embedding_path, client_for_embedding)
    products = load_products(product_catalog_path)
    client = chat_client or ClovaChatClient.from_env()
    return _compile_clova_rag_workflow(
        policy_retriever=policy_retriever,
        product_retriever=product_retriever,
        select_candidates=lambda state: filter_candidate_products(state, products),
        chat_client=client,
    )


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
    return _compile_clova_rag_workflow(
        policy_retriever=policy_retriever,
        product_retriever=product_retriever,
        select_candidates=lambda state: store_candidate_products(
            database_repository.filter_products(state.get("user_conditions", {}))
        ),
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
        "retrieve_product",
        lambda state: retrieve(state, product_retriever, allowed_product_ids=set(state.get("candidate_product_ids", []))),
    )
    graph.add_node("no_matching_product", no_matching_product)
    graph.add_node("retrieve_policy", lambda state: retrieve(state, policy_retriever))
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
        intent_route,
        {"information": "retrieve_policy", "recommendation": "check_recommendation_requirements"},
    )
    graph.add_conditional_edges(
        "check_recommendation_requirements",
        recommendation_requirement_route,
        {"need_more_info": "need_more_info", "filter_products": "filter_candidate_products"},
    )
    graph.add_conditional_edges(
        "filter_candidate_products",
        candidate_product_route,
        {"retrieve_product": "retrieve_product", "no_matching_product": "no_matching_product"},
    )
    graph.add_edge("need_more_info", END)
    graph.add_edge("no_matching_product", END)
    graph.add_edge("retrieve_policy", "generate_answer")
    graph.add_edge("retrieve_product", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()

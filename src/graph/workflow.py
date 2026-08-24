"""RAG만 사용하는 최소 LangGraph 워크플로."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from src.rag.retriever import JsonRagRetriever
from src.rag.naver_embedding import ClovaEmbeddingClient
from src.rag.vector_retriever import EmbeddedJsonRagRetriever
from src.llm.hyperclova import ClovaChatClient

from .nodes import analyze_query, check_scope, generate_clova_answer, grounded_response, out_of_scope_response, retrieve, scope_route
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
):
    """네이버 임베딩 RAG와 CLOVA 최종 답변 생성을 연결한다."""
    retriever = EmbeddedJsonRagRetriever.from_jsonl(
        embedding_path, embedding_client or ClovaEmbeddingClient.from_env()
    )
    client = chat_client or ClovaChatClient.from_env()
    graph = StateGraph(RagGraphState)
    graph.add_node("check_scope", check_scope)
    graph.add_node("out_of_scope", out_of_scope_response)
    graph.add_node("analyze_query", lambda state: analyze_query(state, client))
    graph.add_node("retrieve", lambda state: retrieve(state, retriever))
    graph.add_node("generate_answer", lambda state: generate_clova_answer(state, client))
    graph.add_edge(START, "check_scope")
    graph.add_conditional_edges(
        "check_scope",
        scope_route,
        {"analyze_query": "analyze_query", "out_of_scope": "out_of_scope"},
    )
    graph.add_edge("out_of_scope", END)
    graph.add_edge("analyze_query", "retrieve")
    graph.add_edge("retrieve", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()

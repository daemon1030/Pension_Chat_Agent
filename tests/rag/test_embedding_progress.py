from pathlib import Path

from src.rag.vector_retriever import EmbeddedJsonRagRetriever


class DummyClient:
    def embed(self, text: str) -> list[float]:
        return [1.0]


def test_embedding_retriever_explains_missing_embedding_file(tmp_path):
    missing_path = Path(tmp_path) / "missing.jsonl"

    try:
        EmbeddedJsonRagRetriever.from_jsonl(missing_path, DummyClient())
    except FileNotFoundError as error:
        assert "scripts/rag/build_embeddings.py" in str(error)
    else:
        raise AssertionError("임베딩 파일이 없을 때 FileNotFoundError가 필요합니다.")

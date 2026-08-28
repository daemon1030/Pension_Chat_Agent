from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_schema_contains_class_filter_table_and_pgvector_chunk_table():
    schema = (PROJECT_ROOT / "database" / "init.sql").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "CREATE TABLE IF NOT EXISTS product_classes" in schema
    assert "eligible_account_types TEXT[]" in schema
    assert "CREATE TABLE IF NOT EXISTS rag_chunks" in schema
    assert "embedding VECTOR(1024)" in schema
    assert "vector_cosine_ops" in schema
    assert "product_id TEXT," in schema

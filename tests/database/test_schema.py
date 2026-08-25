from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_schema_contains_relational_product_table_and_pgvector_chunk_table():
    schema = (PROJECT_ROOT / "database" / "init.sql").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "CREATE TABLE IF NOT EXISTS pension_products" in schema
    assert "CREATE TABLE IF NOT EXISTS rag_chunks" in schema
    assert "embedding VECTOR(1024)" in schema
    assert "vector_cosine_ops" in schema
    assert "REFERENCES pension_products(product_id)" in schema

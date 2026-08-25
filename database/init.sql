CREATE EXTENSION IF NOT EXISTS vector;

-- 정확한 조건 필터링에 쓰는 일반 관계형 상품 테이블
CREATE TABLE IF NOT EXISTS pension_products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
    min_age INTEGER NOT NULL DEFAULT 0 CHECK (min_age >= 0),
    max_age INTEGER,
    risk_level TEXT,
    allowed_employment TEXT[] NOT NULL DEFAULT '{}',
    allowed_risk_preferences TEXT[] NOT NULL DEFAULT '{}',
    goals TEXT[] NOT NULL DEFAULT '{}',
    fee_rate NUMERIC(8, 5),
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_name TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (max_age IS NULL OR max_age >= min_age)
);

CREATE INDEX IF NOT EXISTS pension_products_active_idx
    ON pension_products (status);

-- 규정과 상품 설명을 함께 저장하는 벡터 테이블
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    knowledge_type TEXT NOT NULL CHECK (knowledge_type IN ('POLICY', 'PRODUCT')),
    product_id TEXT REFERENCES pension_products(product_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    document_title TEXT,
    section_id TEXT NOT NULL,
    section_title TEXT,
    topic TEXT,
    content TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (knowledge_type = 'POLICY' AND product_id IS NULL)
        OR (knowledge_type = 'PRODUCT' AND product_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS rag_chunks_knowledge_type_idx
    ON rag_chunks (knowledge_type);
CREATE INDEX IF NOT EXISTS rag_chunks_product_id_idx
    ON rag_chunks (product_id);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);

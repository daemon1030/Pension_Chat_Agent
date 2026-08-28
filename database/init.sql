CREATE EXTENSION IF NOT EXISTS vector;

-- 사용자가 실제로 가입하는 단위인 상품 클래스를 한 행으로 저장한다.
-- 상품 공통 정보는 클래스마다 반복해, 추천 필터를 한 번의 조회로 끝낸다.
CREATE TABLE IF NOT EXISTS product_classes (
    class_id TEXT PRIMARY KEY,
    class_name TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    risk_grade INTEGER CHECK (risk_grade BETWEEN 1 AND 6),
    asset_type TEXT NOT NULL DEFAULT 'OTHER',
    investment_region TEXT NOT NULL DEFAULT 'UNKNOWN',
    eligible_account_types TEXT[] NOT NULL DEFAULT '{}',
    sales_channel TEXT NOT NULL DEFAULT 'UNKNOWN',
    capital_protection TEXT NOT NULL DEFAULT 'UNKNOWN',
    redemption_available TEXT NOT NULL DEFAULT 'UNKNOWN',
    redemption_fee_type TEXT NOT NULL DEFAULT 'UNKNOWN',
    total_fee_rate NUMERIC(8, 5),
    upfront_fee_rate NUMERIC(8, 5),
    status TEXT NOT NULL DEFAULT 'UNKNOWN',
    source_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (asset_type IN ('EQUITY', 'BOND', 'MIXED', 'MMF', 'ETF', 'REIT', 'DERIVATIVE', 'OTHER')),
    CHECK (investment_region IN ('DOMESTIC', 'OVERSEAS', 'GLOBAL', 'MIXED', 'UNKNOWN')),
    CHECK (sales_channel IN ('ONLINE', 'OFFLINE', 'ONLINE_SUPER', 'INSTITUTIONAL', 'WRAP_TRUST', 'UNKNOWN')),
    CHECK (capital_protection IN ('TRUE', 'FALSE', 'UNKNOWN')),
    CHECK (redemption_available IN ('TRUE', 'FALSE', 'CONDITIONAL', 'UNKNOWN')),
    CHECK (redemption_fee_type IN ('NONE', 'FIXED_RATE', 'CONDITIONAL', 'UNKNOWN')),
    CHECK (status IN ('ON_SALE', 'SUSPENDED', 'ENDED', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS product_classes_filter_idx
    ON product_classes (status, risk_grade, sales_channel);
CREATE INDEX IF NOT EXISTS product_classes_product_id_idx
    ON product_classes (product_id);
CREATE INDEX IF NOT EXISTS product_classes_account_types_idx
    ON product_classes USING gin (eligible_account_types);

-- 규정과 상품 설명을 함께 저장하는 벡터 테이블
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    knowledge_type TEXT NOT NULL CHECK (knowledge_type IN ('POLICY', 'PRODUCT')),
    -- product_id는 product_classes의 여러 클래스를 묶는 값이므로 FK로 두지 않는다.
    product_id TEXT,
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

-- 이미 만들어진 로컬 DB를 새 클래스 기반 필터 구조로 옮길 때 한 번 실행한다.
-- 기존 pension_products 데이터는 삭제하지 않는다.

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

ALTER TABLE rag_chunks DROP CONSTRAINT IF EXISTS rag_chunks_product_id_fkey;

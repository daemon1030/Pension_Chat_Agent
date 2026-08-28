from src.database.repository import PostgresPensionRepository


class CursorResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class RecordingConnection:
    def __init__(self, rows=()):
        self.rows = rows
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return CursorResult(self.rows)


def test_vector_literal_requires_clova_embedding_dimension():
    repository = PostgresPensionRepository(RecordingConnection())

    assert repository.vector_literal([1.0] * 1024).startswith("[1.0,1.0")

    try:
        repository.vector_literal([1.0])
    except ValueError as error:
        assert "1024차원" in str(error)
    else:
        raise AssertionError("잘못된 차원의 임베딩은 거부해야 합니다.")


def test_product_class_filter_uses_account_and_risk_conditions_in_sql():
    connection = RecordingConnection(rows=[(
        "BH807", "C-Pe", "B5517", "안정형 상품", 6,
        "BOND", "DOMESTIC", ["PENSION_SAVINGS"], "ONLINE",
        "FALSE", "TRUE", "NONE", 0.185, 0.0, "ON_SALE", 9,
    )])
    repository = PostgresPensionRepository(connection)

    result = repository.filter_product_classes({
        "account_type": "PENSION_SAVINGS",
        "risk_preference": "CONSERVATIVE",
        "sales_channel": "ONLINE",
    })

    assert result[0]["class_id"] == "BH807"
    assert "ANY(eligible_account_types)" in connection.calls[0][0]
    assert connection.calls[0][1]["min_risk_grade"] == 5
    assert connection.calls[0][1]["max_risk_grade"] == 6


def test_product_vector_search_returns_before_query_when_no_candidates():
    connection = RecordingConnection()
    repository = PostgresPensionRepository(connection)

    result = repository.search_chunks([1.0] * 1024, knowledge_type="PRODUCT", allowed_product_ids=[])

    assert result == []
    assert connection.calls == []


def test_policy_vector_search_does_not_require_product_ids():
    connection = RecordingConnection(rows=[(
        "POLICY_001", "DOC_001", "연금 규정", "SEC_001", "세액공제", "규정",
        "규정 내용", 1, 1, "PASS", None, 0.91,
    )])
    repository = PostgresPensionRepository(connection)

    result = repository.search_chunks([1.0] * 1024, knowledge_type="POLICY")

    assert result[0]["product_id"] is None
    assert connection.calls[0][1]["allowed_product_ids"] is None


def test_product_vector_search_can_limit_evidence_per_product():
    connection = RecordingConnection()
    repository = PostgresPensionRepository(connection)

    repository.search_chunks(
        [1.0] * 1024,
        knowledge_type="PRODUCT",
        top_k=40,
        allowed_product_ids=["P001", "P002"],
        per_product_limit=2,
    )

    query, params = connection.calls[0]
    assert "ROW_NUMBER() OVER" in query
    assert "PARTITION BY product_id" in query
    assert params["per_product_limit"] == 2

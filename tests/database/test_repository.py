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


def test_product_filter_uses_exact_user_conditions_in_sql():
    connection = RecordingConnection(rows=[(
        "PENSION_PRODUCT_001", "안정형 상품", "ACTIVE", 19, None, "LOW",
        ["EMPLOYED"], ["CONSERVATIVE"], ["RETIREMENT_PREPARATION"], None, {},
    )])
    repository = PostgresPensionRepository(connection)

    result = repository.filter_products({
        "age": 20,
        "employment_status": "EMPLOYED",
        "risk_preference": "CONSERVATIVE",
        "goal": "RETIREMENT_PREPARATION",
    })

    assert result[0]["product_id"] == "PENSION_PRODUCT_001"
    assert "ANY(allowed_risk_preferences)" in connection.calls[0][0]
    assert connection.calls[0][1]["age"] == 20


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

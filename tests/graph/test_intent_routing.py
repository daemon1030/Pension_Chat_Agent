import json

from src.graph.workflow import create_clova_rag_workflow
from src.llm.schemas import QueryAnalysis, RagAnswer


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]


class FakeChatClient:
    def __init__(self, analysis: QueryAnalysis) -> None:
        self.analysis = analysis
        self.answer_prompts: list[str] = []

    def generate_query_analysis(self, **kwargs) -> QueryAnalysis:
        return self.analysis

    def generate_rag_answer(self, *, user_prompt: str, **kwargs) -> RagAnswer:
        self.answer_prompts.append(user_prompt)
        return RagAnswer(status="ANSWER", answer="근거 기반 답변입니다.")


def write_embedding(path, *, document_id: str, content: str, product_id: str | None = None) -> None:
    record = {
        "chunk_id": f"{document_id}_CHUNK001", "document_id": document_id, "document_title": document_id,
        "section_id": "SEC_001", "section_title": "개요", "topic": "연금", "content": content,
        "page_start": 1, "page_end": 1, "validation_status": "PASS", "embedding": [1.0, 0.0],
    }
    if product_id:
        record["product_id"] = product_id
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


def make_workflow(tmp_path, analysis: QueryAnalysis):
    policy_path = tmp_path / "policy.jsonl"
    product_path = tmp_path / "product.jsonl"
    catalog_path = tmp_path / "products.json"
    write_embedding(policy_path, document_id="POLICY_001", content="연금 제도 일반 규정")
    write_embedding(product_path, document_id="PRODUCT_001", content="안정형 데모 연금상품", product_id="PENSION_PRODUCT_DEMO_001")
    catalog_path.write_text(json.dumps({"products": [{
        "product_id": "PENSION_PRODUCT_DEMO_001", "product_name": "안정형 데모 연금상품",
        "status": "ACTIVE", "min_age": 19, "allowed_employment": ["EMPLOYED"],
        "allowed_risk_preferences": ["CONSERVATIVE"], "goals": ["RETIREMENT_PREPARATION"],
    }]}, ensure_ascii=False), encoding="utf-8")
    embeddings = FakeEmbeddingClient()
    chat = FakeChatClient(analysis)
    return create_clova_rag_workflow(
        policy_path,
        embeddings,
        chat,
        product_embedding_path=product_path,
        product_catalog_path=catalog_path,
    ), chat


def test_information_intent_searches_policy_rag(tmp_path):
    workflow, chat = make_workflow(tmp_path, QueryAnalysis(intent="PENSION_INFO"))

    result = workflow.invoke({"query": "연금저축이 뭐야?"})

    assert result["status"] == "ANSWER"
    assert result["sources"][0]["document_id"] == "POLICY_001"
    assert "candidate_products" in chat.answer_prompts[0]


def test_recommendation_intent_filters_catalog_then_searches_product_rag(tmp_path):
    workflow, chat = make_workflow(tmp_path, QueryAnalysis(
        intent="PENSION_RECOMMENDATION",
        user_conditions={
            "age": 20,
            "employment_status": "EMPLOYED",
            "risk_preference": "CONSERVATIVE",
            "goal": "RETIREMENT_PREPARATION",
        },
    ))

    result = workflow.invoke({"query": "안전한 연금상품을 추천해줘"})

    assert result["status"] == "ANSWER"
    assert result["candidate_product_ids"] == ["PENSION_PRODUCT_DEMO_001"]
    assert result["sources"][0]["document_id"] == "PRODUCT_001"
    assert "PENSION_PRODUCT_DEMO_001" in chat.answer_prompts[0]


def test_recommendation_intent_asks_for_missing_conditions_before_rag_search(tmp_path):
    workflow, chat = make_workflow(tmp_path, QueryAnalysis(
        intent="PENSION_RECOMMENDATION",
        user_conditions={"age": 20},
    ))

    result = workflow.invoke({"query": "연금 추천해줘"})

    assert result["status"] == "NEED_MORE_INFO"
    assert result["missing_fields"] == ["고용 형태", "투자 위험 선호", "연금 준비 목적"]
    assert chat.answer_prompts == []

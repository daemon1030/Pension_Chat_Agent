from fastapi.testclient import TestClient

from src.api.main import app, get_workflow


class FakeWorkflow:
    def invoke(self, state):
        assert state == {"query": "IRP는 어떤 제도야?", "top_k": 5}
        return {
            "scope": "IN_SCOPE",
            "intent": "PENSION_INFO",
            "retrieval_sources": ["POLICY_RAG"],
            "status": "ANSWER",
            "answer": "IRP는 개인형 퇴직연금 제도입니다.",
            "retrieved_chunks": [
                {"document_id": "DOC_014", "page_start": 1, "content": "IRP 설명"},
                {"document_id": "DOC_014", "page_start": 1, "content": "같은 페이지의 다른 청크"},
            ],
        }


def test_answer_returns_the_question_id_and_grounded_answer():
    app.dependency_overrides[get_workflow] = lambda: FakeWorkflow()
    try:
        response = TestClient(app).get(
            "/answer",
            params={"question_id": "sample-001", "question": "IRP는 어떤 제도야?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "question_id": "sample-001",
        "question": "IRP는 어떤 제도야?",
        "retrieved_context": [{"document_id": "DOC_014", "page": 1}],
        "think_trace": "연금 정보 질문으로 분류 → POLICY_RAG 문서 2건 검색 → 근거 기반 답변 생성",
        "answer": "IRP는 개인형 퇴직연금 제도입니다.",
    }

from src.llm.schemas import RagAnswer
from src.graph.nodes import generate_clova_answer


class FakeChatClient:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def generate_rag_answer(self, *, system_prompt: str, user_prompt: str) -> RagAnswer:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return RagAnswer(status="ANSWER", answer="문서 근거에 따른 답변입니다.")


def test_clova_answer_receives_rag_context_and_returns_sources():
    client = FakeChatClient()
    state = {
        "query": "언제 수령할 수 있나요?",
        "retrieved_chunks": [{
            "document_id": "DOC_001", "document_title": "연금 안내", "section_id": "SEC_001",
            "section_title": "수령 조건", "topic": "연금 수령", "content": "만 55세 이후 수령 가능합니다.",
            "page_start": 3, "validation_status": "PASS",
        }],
    }

    result = generate_clova_answer(state, client)

    assert result["answer"] == "문서 근거에 따른 답변입니다."
    assert "만 55세 이후" in client.user_prompt
    assert "근거에 없는" in client.system_prompt
    assert result["sources"][0]["page"] == 3


def test_clova_returns_missing_fields_and_follow_up_question():
    class MissingInfoClient(FakeChatClient):
        def generate_rag_answer(self, *, system_prompt: str, user_prompt: str) -> RagAnswer:
            return RagAnswer(
                status="NEED_MORE_INFO",
                answer="개인별 절세 효과를 판단하려면 소득 정보가 필요합니다.",
                missing_fields=["소득 유형", "연간 소득"],
                follow_up_question="현재 소득 유형과 연간 소득을 알려주세요.",
            )

    result = generate_clova_answer({"query": "나에게 좋은 연금 추천해줘", "retrieved_chunks": [{"document_id": "DOC_001", "section_id": "SEC_001", "content": "연금 안내", "page_start": 1}]}, MissingInfoClient())

    assert result["status"] == "NEED_MORE_INFO"
    assert result["missing_fields"] == ["소득 유형", "연간 소득"]
    assert result["follow_up_question"] == "현재 소득 유형과 연간 소득을 알려주세요."


def test_missing_follow_up_question_is_completed_from_missing_fields():
    response = RagAnswer.model_validate({
        "status": "NEED_MORE_INFO",
        "answer": "개인별 추천을 위해 정보가 필요합니다.",
        "missing_information": ["나이", "투자 위험 선호"],
    })

    assert response.missing_fields == ["나이", "투자 위험 선호"]
    assert response.follow_up_question == "다음 정보를 알려주세요: 나이, 투자 위험 선호."


def test_string_additional_info_is_normalized_to_missing_fields():
    response = RagAnswer.model_validate({
        "status": "NEED_MORE_INFO",
        "answer": "추천을 위해 정보가 필요합니다.",
        "additional_info": "나이, 소득 유형/기존 연금 가입 여부",
    })

    assert response.missing_fields == ["나이", "소득 유형", "기존 연금 가입 여부"]


def test_bulleted_missing_information_in_answer_is_normalized():
    response = RagAnswer.model_validate({
        "status": "NEED_MORE_INFO",
        "answer": "추천을 위해 다음 정보가 필요합니다.\n- 나이\n- 소득 유형 및 금액\n- 투자 위험 선호도",
    })

    assert response.missing_fields == ["나이", "소득 유형 및 금액", "투자 위험 선호도"]
    assert response.follow_up_question == "다음 정보를 알려주세요: 나이, 소득 유형 및 금액, 투자 위험 선호도."


def test_missing_fields_are_limited_to_three_for_first_follow_up():
    response = RagAnswer.model_validate({
        "status": "NEED_MORE_INFO",
        "answer": "추가 정보가 필요합니다.",
        "missing_fields": ["나이", "소득 유형", "기존 연금", "고용 형태"],
    })

    assert response.missing_fields == ["나이", "소득 유형", "기존 연금"]


def test_clova_is_not_called_when_no_context():
    result = generate_clova_answer({"query": "모르는 질문", "retrieved_chunks": []}, FakeChatClient())

    assert result["status"] == "NO_GROUNDED_CONTEXT"

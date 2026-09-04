from src.llm.hyperclova import ClovaChatClient, ClovaChatSettings


class RetryClient(ClovaChatClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(ClovaChatSettings(api_key="Bearer test", json_retry_count=1))
        self.responses = responses
        self.prompts: list[tuple[str, str]] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_invalid_json_is_retried_with_repair_instruction():
    client = RetryClient([
        "정보가 부족합니다.",
        '{"status":"NEED_MORE_INFO","answer":"나이가 필요합니다.","missing_fields":["나이"],"follow_up_question":"현재 나이를 알려주세요."}',
    ])

    result = client.generate_rag_answer(system_prompt="원래 지시", user_prompt="원래 질문")

    assert result.status == "NEED_MORE_INFO"
    assert len(client.prompts) == 2
    assert "JSON Schema" in client.prompts[1][0]
    assert "직전 형식 오류 응답" in client.prompts[1][1]


def test_stage_model_setting_falls_back_to_the_shared_model(monkeypatch):
    monkeypatch.setenv("CLOVASTUDIO_API_KEY", "test-key")
    monkeypatch.setenv("CLOVASTUDIO_CHAT_MODEL", "shared-model")
    monkeypatch.delenv("CLOVASTUDIO_ANALYSIS_MODEL", raising=False)

    settings = ClovaChatSettings.from_env(model_env_name="CLOVASTUDIO_ANALYSIS_MODEL")

    assert settings.model == "shared-model"


def test_stage_model_setting_prefers_its_own_model(monkeypatch):
    monkeypatch.setenv("CLOVASTUDIO_API_KEY", "test-key")
    monkeypatch.setenv("CLOVASTUDIO_CHAT_MODEL", "shared-model")
    monkeypatch.setenv("CLOVASTUDIO_ANSWER_MODEL", "answer-model")

    settings = ClovaChatSettings.from_env(model_env_name="CLOVASTUDIO_ANSWER_MODEL")

    assert settings.model == "answer-model"

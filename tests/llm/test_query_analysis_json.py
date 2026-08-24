from src.llm.hyperclova import ClovaChatClient, ClovaChatSettings


class QueryAnalysisClient(ClovaChatClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(ClovaChatSettings(api_key="Bearer test", json_retry_count=1))
        self.responses = responses
        self.prompts: list[tuple[str, str]] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_query_analysis_retries_then_returns_a_supported_intent_and_condition_object():
    client = QueryAnalysisClient([
        "분석 결과입니다.",
        '{"intent":"PENSION_RECOMMENDATION","user_conditions":{"age":20}}',
    ])

    result = client.generate_query_analysis(system_prompt="원래 분석 지시", user_prompt="원래 질문")

    assert result.intent == "PENSION_RECOMMENDATION"
    assert result.user_conditions == {"age": 20}
    assert len(client.prompts) == 2
    assert "질문 분석 JSON Schema" in client.prompts[1][0]

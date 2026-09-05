from src.llm.hyperclova import ClovaChatApiError, ClovaChatClient, ClovaChatSettings


def test_base_model_uses_model_chat_completions_path():
    client = ClovaChatClient(ClovaChatSettings(api_key="Bearer test", model="HCX-DASH-002"))

    assert client._request_path() == "/v3/chat-completions/HCX-DASH-002"


def test_tuned_model_uses_task_chat_completions_path():
    client = ClovaChatClient(ClovaChatSettings(api_key="Bearer test", model="ft:rdub52j1"))

    assert client._request_path() == "/v3/tasks/rdub52j1/chat-completions"


def test_empty_tuned_model_task_id_is_rejected():
    client = ClovaChatClient(ClovaChatSettings(api_key="Bearer test", model="ft:  "))

    try:
        client._request_path()
    except ClovaChatApiError as error:
        assert "비어" in str(error)
    else:
        raise AssertionError("빈 튜닝 모델 ID가 허용되었습니다.")

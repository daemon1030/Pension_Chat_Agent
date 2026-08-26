from src.observability.langfuse import flush, observe, update_observation


def test_langfuse_is_a_safe_noop_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    with observe("test-step", input={"query": "연금"}) as observation:
        assert observation is None
        update_observation(observation, output={"status": "ANSWER"})

    flush()

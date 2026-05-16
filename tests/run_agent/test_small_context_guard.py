from run_agent import _allow_small_context_model


def test_small_context_allowed_for_local_ollama_url():
    assert _allow_small_context_model("http://127.0.0.1:11434/v1") is True


def test_small_context_not_allowed_for_remote_provider_url():
    assert _allow_small_context_model("https://api.openai.com/v1") is False

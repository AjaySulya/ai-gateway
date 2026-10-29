from gateway.routing.router import merge_call_kwargs
from gateway.schemas.chat import ChatCompletionRequest


def _request(**extra) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        **extra,
    )


def test_only_whitelisted_params_are_forwarded():
    params = _request(
        temperature=0.2,
        seed=42,
        response_format={"type": "json_object"},
        api_base="https://attacker.example/v1",
        api_key="stolen",
        custom_llm_provider="openai",
        headers={"X-Evil": "1"},
        timeout=1,
    ).provider_params()

    assert params["temperature"] == 0.2
    assert params["seed"] == 42
    assert params["response_format"] == {"type": "json_object"}
    assert "api_base" not in params
    assert "api_key" not in params
    assert "custom_llm_provider" not in params
    assert "headers" not in params
    assert "timeout" not in params


def test_none_values_are_not_forwarded():
    params = _request(temperature=None, max_tokens=100).provider_params()
    assert "temperature" not in params
    assert params["max_tokens"] == 100


def test_provider_config_cannot_be_overridden_by_request():
    kwargs = merge_call_kwargs(
        {"api_base": "https://provider.example/v1", "api_version": "2024-02-01"},
        {
            "api_base": "https://attacker.example/v1",
            "api_version": "attacker",
            "temperature": 0.1,
        },
    )

    assert kwargs["api_base"] == "https://provider.example/v1"
    assert kwargs["api_version"] == "2024-02-01"
    assert kwargs["temperature"] == 0.1


def test_provider_only_kwargs_are_stripped_even_without_provider_config():
    kwargs = merge_call_kwargs(
        None,
        {"api_base": "https://attacker.example/v1", "api_key": "secret", "top_p": 0.9},
    )

    assert "api_base" not in kwargs
    assert "api_key" not in kwargs
    assert kwargs["top_p"] == 0.9

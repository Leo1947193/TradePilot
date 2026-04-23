from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.llm.dtos import JsonGenerationRequest, LlmMessage, TextGenerationRequest
from app.services.llm.interfaces import LlmAdapter
from app.services.llm.openrouter_adapter import OpenRouterLlmAdapter


class FakeCompletionsClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeChatClient:
    def __init__(self, response) -> None:
        self.completions = FakeCompletionsClient(response)


class FakeOpenAIClient:
    def __init__(self, response) -> None:
        self.chat = FakeChatClient(response)


@pytest.mark.asyncio
async def test_openrouter_adapter_generate_text_maps_request_and_response() -> None:
    client = FakeOpenAIClient(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="hello from OpenRouter"),
                )
            ],
            model="openai/gpt-5.4-mini",
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        )
    )
    adapter = OpenRouterLlmAdapter(
        api_key="demo-key",
        model="openai/gpt-5.4-mini",
        client=client,
    )

    result = await adapter.generate_text(
        TextGenerationRequest(
            messages=(
                LlmMessage(role="system", content="You are concise."),
                LlmMessage(role="user", content="Say hello."),
            ),
            temperature=0.3,
            max_output_tokens=128,
        )
    )

    assert result.provider == "openrouter"
    assert result.model == "openai/gpt-5.4-mini"
    assert result.text == "hello from OpenRouter"
    assert result.finish_reason == "stop"
    assert result.usage is not None
    assert result.usage.total_tokens == 18
    assert client.chat.completions.calls == [
        {
            "model": "openai/gpt-5.4-mini",
            "messages": [
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "Say hello."},
            ],
            "temperature": 0.3,
            "max_tokens": 128,
            "extra_body": {"reasoning": {"enabled": True}},
        }
    ]


@pytest.mark.asyncio
async def test_openrouter_adapter_generate_json_decodes_json_text() -> None:
    client = FakeOpenAIClient(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='{"summary":"ok","score":0.9}'),
                )
            ],
            model="anthropic/claude-sonnet-4",
            usage=SimpleNamespace(prompt_tokens=9, completion_tokens=12, total_tokens=21),
        )
    )
    adapter = OpenRouterLlmAdapter(
        api_key="demo-key",
        model="anthropic/claude-sonnet-4",
        client=client,
    )

    result = await adapter.generate_json(
        JsonGenerationRequest(
            messages=(LlmMessage(role="user", content="Return JSON only."),),
            json_schema={
                "name": "summary_payload",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "score": {"type": "number"},
                    },
                    "required": ["summary", "score"],
                },
            },
        )
    )

    assert result.provider == "openrouter"
    assert result.model == "anthropic/claude-sonnet-4"
    assert result.data == {"summary": "ok", "score": 0.9}
    assert result.raw_text == '{"summary":"ok","score":0.9}'
    assert client.chat.completions.calls == [
        {
            "model": "anthropic/claude-sonnet-4",
            "messages": [{"role": "user", "content": "Return JSON only."}],
            "temperature": None,
            "max_tokens": None,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "summary_payload",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "score": {"type": "number"},
                        },
                        "required": ["summary", "score"],
                    },
                },
            },
            "extra_body": {"reasoning": {"enabled": True}},
        }
    ]


@pytest.mark.asyncio
async def test_openrouter_adapter_raises_when_choices_are_missing() -> None:
    client = FakeOpenAIClient(SimpleNamespace(choices=[]))
    adapter = OpenRouterLlmAdapter(
        api_key="demo-key",
        model="openai/gpt-5.4-mini",
        client=client,
    )

    with pytest.raises(ValueError, match="choices"):
        await adapter.generate_text(
            TextGenerationRequest(messages=(LlmMessage(role="user", content="hello"),))
        )


def test_llm_adapter_protocol_accepts_openrouter_adapter() -> None:
    adapter = OpenRouterLlmAdapter(
        api_key="demo-key",
        model="openai/gpt-5.4-mini",
    )

    assert isinstance(adapter, LlmAdapter)

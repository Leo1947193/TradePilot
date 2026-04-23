from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.services.llm.dtos import JsonGenerationRequest, LlmMessage, TextGenerationRequest
from app.services.llm.interfaces import LlmAdapter
from app.services.llm.minimax_adapter import MiniMaxLlmAdapter


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
async def test_minimax_adapter_generate_text_maps_request_and_response() -> None:
    client = FakeOpenAIClient(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="hello from MiniMax"),
                )
            ],
            model="MiniMax-M2.5",
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
    )
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-M2.5",
        client=client,
    )

    result = await adapter.generate_text(
        TextGenerationRequest(
            messages=(
                LlmMessage(role="system", content="You are concise."),
                LlmMessage(role="user", content="Say hello."),
            ),
            temperature=0.7,
            max_output_tokens=256,
        )
    )

    assert result.provider == "minimax"
    assert result.model == "MiniMax-M2.5"
    assert result.text == "hello from MiniMax"
    assert result.finish_reason == "stop"
    assert result.usage is not None
    assert result.usage.total_tokens == 30
    assert client.chat.completions.calls == [
        {
            "model": "MiniMax-M2.5",
            "messages": [
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "Say hello."},
            ],
            "temperature": 0.7,
            "max_completion_tokens": 256,
            "extra_body": {"reasoning_split": True},
        }
    ]


@pytest.mark.asyncio
async def test_minimax_adapter_generate_json_decodes_json_text() -> None:
    client = FakeOpenAIClient(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='{"summary":"ok","score":0.8}'),
                )
            ],
            model="MiniMax-Text-01",
            usage=SimpleNamespace(prompt_tokens=8, completion_tokens=9, total_tokens=17),
        )
    )
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-Text-01",
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

    assert result.provider == "minimax"
    assert result.model == "MiniMax-Text-01"
    assert result.data == {"summary": "ok", "score": 0.8}
    assert result.raw_text == '{"summary":"ok","score":0.8}'
    assert client.chat.completions.calls == [
        {
            "model": "MiniMax-Text-01",
            "messages": [{"role": "user", "content": "Return JSON only."}],
            "temperature": None,
            "max_completion_tokens": None,
            "extra_body": {
                "reasoning_split": True,
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
            },
        }
    ]


@pytest.mark.asyncio
async def test_minimax_adapter_raises_when_choices_are_missing() -> None:
    client = FakeOpenAIClient(SimpleNamespace(choices=[]))
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-M2.5",
        client=client,
    )

    with pytest.raises(ValueError, match="choices"):
        await adapter.generate_text(
            TextGenerationRequest(messages=(LlmMessage(role="user", content="hello"),))
        )


def test_llm_adapter_protocol_accepts_minimax_adapter() -> None:
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-M2.5",
    )

    assert isinstance(adapter, LlmAdapter)

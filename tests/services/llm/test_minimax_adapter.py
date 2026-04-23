from __future__ import annotations

import httpx
import pytest

from app.services.llm.dtos import JsonGenerationRequest, LlmMessage, TextGenerationRequest
from app.services.llm.interfaces import LlmAdapter
from app.services.llm.minimax_adapter import MiniMaxLlmAdapter


def _make_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_minimax_adapter_generate_text_maps_request_and_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "hello from MiniMax",
                        },
                    }
                ],
                "model": "MiniMax-M2.5",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
                "base_resp": {
                    "status_code": 0,
                    "status_msg": "",
                },
            },
        )

    client = httpx.AsyncClient(transport=_make_transport(handler))
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

    await client.aclose()

    assert result.provider == "minimax"
    assert result.model == "MiniMax-M2.5"
    assert result.text == "hello from MiniMax"
    assert result.finish_reason == "stop"
    assert result.usage is not None
    assert result.usage.total_tokens == 30
    assert captured["url"] == "https://api.minimax.io/v1/text/chatcompletion_v2"
    assert captured["auth"] == "Bearer demo-key"
    assert '"model":"MiniMax-M2.5"' in str(captured["body"])
    assert '"max_completion_tokens":256' in str(captured["body"])


@pytest.mark.asyncio
async def test_minimax_adapter_generate_json_decodes_json_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"summary":"ok","score":0.8}',
                        },
                    }
                ],
                "model": "MiniMax-Text-01",
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 9,
                    "total_tokens": 17,
                },
                "base_resp": {
                    "status_code": 0,
                    "status_msg": "",
                },
            },
        )

    client = httpx.AsyncClient(transport=_make_transport(handler))
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

    await client.aclose()

    assert result.provider == "minimax"
    assert result.model == "MiniMax-Text-01"
    assert result.data == {"summary": "ok", "score": 0.8}
    assert result.raw_text == '{"summary":"ok","score":0.8}'


@pytest.mark.asyncio
async def test_minimax_adapter_raises_on_non_zero_base_resp_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "should not be accepted",
                        },
                    }
                ],
                "base_resp": {
                    "status_code": 1004,
                    "status_msg": "quota exceeded",
                },
            },
        )

    client = httpx.AsyncClient(transport=_make_transport(handler))
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-M2.5",
        client=client,
    )

    with pytest.raises(RuntimeError, match="quota exceeded"):
        await adapter.generate_text(
            TextGenerationRequest(messages=(LlmMessage(role="user", content="hello"),))
        )

    await client.aclose()


def test_llm_adapter_protocol_accepts_minimax_adapter() -> None:
    adapter = MiniMaxLlmAdapter(
        api_key="demo-key",
        model="MiniMax-M2.5",
    )

    assert isinstance(adapter, LlmAdapter)

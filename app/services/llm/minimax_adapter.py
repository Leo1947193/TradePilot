from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

from app.services.llm.dtos import (
    JsonGenerationRequest,
    JsonGenerationResult,
    LlmMessage,
    LlmUsage,
    TextGenerationRequest,
    TextGenerationResult,
)


class MiniMaxLlmAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.minimax.io/v1",
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def generate_text(
        self,
        request: TextGenerationRequest,
    ) -> TextGenerationResult:
        payload = self._build_payload(
            messages=request.messages,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
        )
        body = await self._post_chat_completion(payload)
        return TextGenerationResult(
            provider="minimax",
            model=self._model,
            text=self._extract_text(body),
            finish_reason=self._extract_finish_reason(body),
            usage=self._extract_usage(body),
        )

    async def generate_json(
        self,
        request: JsonGenerationRequest,
    ) -> JsonGenerationResult:
        payload = self._build_payload(
            messages=request.messages,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            json_schema=request.json_schema,
        )
        body = await self._post_chat_completion(payload)
        raw_text = self._extract_text(body)
        return JsonGenerationResult.from_text(
            provider="minimax",
            model=self._model,
            raw_text=raw_text,
            finish_reason=self._extract_finish_reason(body),
            usage=self._extract_usage(body),
        )

    def _build_payload(
        self,
        *,
        messages: tuple[LlmMessage, ...],
        temperature: float | None,
        max_output_tokens: int | None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_output_tokens is not None:
            payload["max_completion_tokens"] = max_output_tokens
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        return payload

    async def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._get_client() as client:
            response = await client.post(
                f"{self._base_url}/text/chatcompletion_v2",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            body = response.json()

        base_resp = body.get("base_resp")
        if isinstance(base_resp, dict) and base_resp.get("status_code", 0) not in (0, None):
            raise RuntimeError(base_resp.get("status_msg") or "MiniMax returned a non-zero status_code")

        return body

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            yield client

    def _extract_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("MiniMax response did not include choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("MiniMax response choice did not include a message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("MiniMax response message content is missing")
        return content

    def _extract_finish_reason(self, body: dict[str, Any]) -> str | None:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        finish_reason = choices[0].get("finish_reason")
        return str(finish_reason) if isinstance(finish_reason, str) else None

    def _extract_usage(self, body: dict[str, Any]) -> LlmUsage | None:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return None
        return LlmUsage(
            prompt_tokens=_as_non_negative_int(usage.get("prompt_tokens")),
            completion_tokens=_as_non_negative_int(usage.get("completion_tokens")),
            total_tokens=_as_non_negative_int(usage.get("total_tokens")),
        )


def _as_non_negative_int(value: Any) -> int | None:
    if not isinstance(value, int) or value < 0:
        return None
    return value

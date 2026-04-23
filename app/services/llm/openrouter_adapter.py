from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.services.llm.dtos import (
    JsonGenerationRequest,
    JsonGenerationResult,
    LlmMessage,
    LlmUsage,
    TextGenerationRequest,
    TextGenerationResult,
)


class OpenRouterLlmAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 8.0,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            base_url=self._base_url,
            timeout=timeout_seconds,
        )

    async def generate_text(
        self,
        request: TextGenerationRequest,
    ) -> TextGenerationResult:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(request.messages),
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
            extra_body={"reasoning": {"enabled": True}},
        )
        return TextGenerationResult(
            provider="openrouter",
            model=self._extract_model(response),
            text=self._extract_text(response),
            finish_reason=self._extract_finish_reason(response),
            usage=self._extract_usage(response),
        )

    async def generate_json(
        self,
        request: JsonGenerationRequest,
    ) -> JsonGenerationResult:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(request.messages),
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
            response_format=(
                {
                    "type": "json_schema",
                    "json_schema": request.json_schema,
                }
                if request.json_schema is not None
                else None
            ),
            extra_body={"reasoning": {"enabled": True}},
        )
        raw_text = self._extract_text(response)
        return JsonGenerationResult.from_text(
            provider="openrouter",
            model=self._extract_model(response),
            raw_text=raw_text,
            finish_reason=self._extract_finish_reason(response),
            usage=self._extract_usage(response),
        )

    def _build_messages(self, messages: tuple[LlmMessage, ...]) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    def _extract_text(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError("OpenRouter response did not include choices")

        message = getattr(choices[0], "message", None)
        if message is None:
            raise ValueError("OpenRouter response choice did not include a message")

        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str) and text:
                    text_parts.append(text)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            if text_parts:
                return "".join(text_parts)

        raise ValueError("OpenRouter response message content is missing")

    def _extract_finish_reason(self, response: Any) -> str | None:
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        finish_reason = getattr(choices[0], "finish_reason", None)
        return str(finish_reason) if isinstance(finish_reason, str) else None

    def _extract_usage(self, response: Any) -> LlmUsage | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return LlmUsage(
            prompt_tokens=_as_non_negative_int(getattr(usage, "prompt_tokens", None)),
            completion_tokens=_as_non_negative_int(getattr(usage, "completion_tokens", None)),
            total_tokens=_as_non_negative_int(getattr(usage, "total_tokens", None)),
        )

    def _extract_model(self, response: Any) -> str:
        model = getattr(response, "model", None)
        return str(model) if isinstance(model, str) and model else self._model


def _as_non_negative_int(value: Any) -> int | None:
    if not isinstance(value, int) or value < 0:
        return None
    return value

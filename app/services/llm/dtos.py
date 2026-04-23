from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LlmDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LlmMessage(LlmDto):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LlmUsage(LlmDto):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class TextGenerationRequest(LlmDto):
    messages: tuple[LlmMessage, ...] = Field(min_length=1)
    temperature: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int | None = Field(default=None, ge=1)


class JsonGenerationRequest(LlmDto):
    messages: tuple[LlmMessage, ...] = Field(min_length=1)
    json_schema: dict[str, Any] | None = None
    temperature: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int | None = Field(default=None, ge=1)


class TextGenerationResult(LlmDto):
    provider: str
    model: str
    text: str
    finish_reason: str | None = None
    usage: LlmUsage | None = None


class JsonGenerationResult(LlmDto):
    provider: str
    model: str
    data: dict[str, Any] | list[Any]
    finish_reason: str | None = None
    usage: LlmUsage | None = None
    raw_text: str

    @classmethod
    def from_text(
        cls,
        *,
        provider: str,
        model: str,
        raw_text: str,
        finish_reason: str | None = None,
        usage: LlmUsage | None = None,
    ) -> "JsonGenerationResult":
        parsed = json.loads(raw_text)
        if not isinstance(parsed, (dict, list)):
            raise ValueError("LLM JSON result must decode to an object or array")
        return cls(
            provider=provider,
            model=model,
            data=parsed,
            finish_reason=finish_reason,
            usage=usage,
            raw_text=raw_text,
        )

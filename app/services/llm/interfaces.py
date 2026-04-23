from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.llm.dtos import (
    JsonGenerationRequest,
    JsonGenerationResult,
    TextGenerationRequest,
    TextGenerationResult,
)


@runtime_checkable
class LlmAdapter(Protocol):
    async def generate_text(
        self,
        request: TextGenerationRequest,
    ) -> TextGenerationResult:
        ...

    async def generate_json(
        self,
        request: JsonGenerationRequest,
    ) -> JsonGenerationResult:
        ...

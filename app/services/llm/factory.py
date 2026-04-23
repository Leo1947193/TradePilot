from __future__ import annotations

from app.config import Settings
from app.services.llm.interfaces import LlmAdapter
from app.services.llm.minimax_adapter import MiniMaxLlmAdapter


class LlmProviderConfigurationError(RuntimeError):
    pass


def build_llm_adapter(settings: Settings) -> LlmAdapter:
    provider = (settings.llm_provider or "").strip().lower()
    if not provider:
        raise LlmProviderConfigurationError("LLM_PROVIDER is required to build an LLM adapter")

    if provider != "minimax":
        raise LlmProviderConfigurationError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")

    if settings.llm_model is None or not settings.llm_model.strip():
        raise LlmProviderConfigurationError("LLM_MODEL is required for MiniMax")
    if settings.minimax_api_key is None or not settings.minimax_api_key.strip():
        raise LlmProviderConfigurationError("MINIMAX_API_KEY is required for MiniMax")

    return MiniMaxLlmAdapter(
        api_key=settings.minimax_api_key,
        model=settings.llm_model,
        base_url=settings.minimax_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )

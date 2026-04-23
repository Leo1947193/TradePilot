from __future__ import annotations

import pytest

from app.config import Settings
from app.services.llm.factory import LlmProviderConfigurationError, build_llm_adapter
from app.services.llm.minimax_adapter import MiniMaxLlmAdapter


def test_settings_include_llm_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@localhost:5432/tradepilot")
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("LLM_MODEL", "MiniMax-M2.5")
    monkeypatch.setenv("MINIMAX_API_KEY", "demo-key")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")

    settings = Settings()

    assert settings.llm_provider == "minimax"
    assert settings.llm_model == "MiniMax-M2.5"
    assert settings.minimax_api_key == "demo-key"
    assert settings.minimax_base_url == "https://api.minimax.io/v1"


def test_build_llm_adapter_requires_provider() -> None:
    settings = Settings(postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot")

    with pytest.raises(LlmProviderConfigurationError, match="LLM_PROVIDER"):
        build_llm_adapter(settings)


def test_build_llm_adapter_rejects_unsupported_provider() -> None:
    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        llm_provider="unsupported",
    )

    with pytest.raises(LlmProviderConfigurationError, match="unsupported LLM_PROVIDER"):
        build_llm_adapter(settings)


def test_build_llm_adapter_requires_model_and_minimax_api_key() -> None:
    missing_model = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        llm_provider="minimax",
        minimax_api_key="demo-key",
    )
    with pytest.raises(LlmProviderConfigurationError, match="LLM_MODEL"):
        build_llm_adapter(missing_model)

    missing_key = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        llm_provider="minimax",
        llm_model="MiniMax-M2.5",
    )
    with pytest.raises(LlmProviderConfigurationError, match="MINIMAX_API_KEY"):
        build_llm_adapter(missing_key)


def test_build_llm_adapter_returns_minimax_adapter() -> None:
    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        llm_provider="minimax",
        llm_model="MiniMax-M2.5",
        minimax_api_key="demo-key",
        request_timeout_seconds=12.0,
    )

    adapter = build_llm_adapter(settings)

    assert isinstance(adapter, MiniMaxLlmAdapter)
    assert adapter._model == "MiniMax-M2.5"
    assert adapter._timeout_seconds == 12.0

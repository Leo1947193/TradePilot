from __future__ import annotations

from app.graph.nodes.run_sentiment import (
    SENTIMENT_DEGRADED_REASON,
    SENTIMENT_DEGRADED_SUMMARY,
    SENTIMENT_DEGRADED_WARNING,
    run_sentiment,
)
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_sentiment_writes_degraded_module_result() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.sentiment is not None
    assert state.module_results.sentiment.module == AnalysisModuleName.SENTIMENT
    assert state.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.sentiment.low_confidence is True
    assert state.module_results.sentiment.summary == SENTIMENT_DEGRADED_SUMMARY
    assert state.module_results.sentiment.reason == SENTIMENT_DEGRADED_REASON


def test_run_sentiment_updates_diagnostics_without_duplicates() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["sentiment"]
    assert state.diagnostics.warnings == [SENTIMENT_DEGRADED_WARNING]


def test_run_sentiment_preserves_unrelated_state() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_789",
            "context": {
                "market": "US",
                "benchmark": "SPY",
                "analysis_window_days": [7, 90],
            },
            "module_results": {
                "technical": {
                    "status": "usable",
                    "summary": "Trend remains constructive.",
                    "direction": "bullish",
                    "data_completeness_pct": 95,
                }
            },
            "diagnostics": {
                "excluded_modules": ["event"],
                "warnings": ["existing warning"],
            },
        }
    )

    assert state.request_id == "req_789"
    assert state.context.market == "US"
    assert state.module_results.technical is not None
    assert state.module_results.technical.module == "technical"
    assert state.diagnostics.excluded_modules == ["event"]
    assert state.diagnostics.warnings == ["existing warning", SENTIMENT_DEGRADED_WARNING]


def test_run_sentiment_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_sentiment(initial_state)
    second_run = run_sentiment(first_run)

    assert second_run.diagnostics.degraded_modules == ["sentiment"]
    assert second_run.diagnostics.warnings == [SENTIMENT_DEGRADED_WARNING]
    assert second_run.module_results.sentiment is not None
    assert second_run.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED

from __future__ import annotations

from app.graph.nodes.run_fundamental import (
    FUNDAMENTAL_DEGRADED_REASON,
    FUNDAMENTAL_DEGRADED_SUMMARY,
    FUNDAMENTAL_DEGRADED_WARNING,
    run_fundamental,
)
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_fundamental_writes_degraded_module_result() -> None:
    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.fundamental is not None
    assert state.module_results.fundamental.module == AnalysisModuleName.FUNDAMENTAL
    assert state.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.fundamental.low_confidence is True
    assert state.module_results.fundamental.summary == FUNDAMENTAL_DEGRADED_SUMMARY
    assert state.module_results.fundamental.reason == FUNDAMENTAL_DEGRADED_REASON


def test_run_fundamental_updates_diagnostics_without_duplicates() -> None:
    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["fundamental"]
    assert state.diagnostics.warnings == [FUNDAMENTAL_DEGRADED_WARNING]


def test_run_fundamental_preserves_unrelated_state() -> None:
    state = run_fundamental(
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
    assert state.diagnostics.warnings == ["existing warning", FUNDAMENTAL_DEGRADED_WARNING]


def test_run_fundamental_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_fundamental(initial_state)
    second_run = run_fundamental(first_run)

    assert second_run.diagnostics.degraded_modules == ["fundamental"]
    assert second_run.diagnostics.warnings == [FUNDAMENTAL_DEGRADED_WARNING]
    assert second_run.module_results.fundamental is not None
    assert second_run.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED

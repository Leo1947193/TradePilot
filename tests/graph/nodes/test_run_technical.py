from __future__ import annotations

from app.graph.nodes.run_technical import (
    TECHNICAL_DEGRADED_REASON,
    TECHNICAL_DEGRADED_SUMMARY,
    TECHNICAL_DEGRADED_WARNING,
    run_technical,
)
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_technical_writes_degraded_module_result() -> None:
    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.technical is not None
    assert state.module_results.technical.module == AnalysisModuleName.TECHNICAL
    assert state.module_results.technical.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.technical.low_confidence is True
    assert state.module_results.technical.summary == TECHNICAL_DEGRADED_SUMMARY
    assert state.module_results.technical.reason == TECHNICAL_DEGRADED_REASON


def test_run_technical_updates_diagnostics_without_duplicates() -> None:
    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["technical"]
    assert state.diagnostics.warnings == [TECHNICAL_DEGRADED_WARNING]


def test_run_technical_preserves_unrelated_state() -> None:
    state = run_technical(
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
                "fundamental": {
                    "status": "usable",
                    "summary": "Fundamentals remain stable.",
                    "direction": "neutral",
                    "data_completeness_pct": 92,
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
    assert state.module_results.fundamental is not None
    assert state.module_results.fundamental.module == "fundamental"
    assert state.diagnostics.excluded_modules == ["event"]
    assert state.diagnostics.warnings == ["existing warning", TECHNICAL_DEGRADED_WARNING]


def test_run_technical_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_technical(initial_state)
    second_run = run_technical(first_run)

    assert second_run.diagnostics.degraded_modules == ["technical"]
    assert second_run.diagnostics.warnings == [TECHNICAL_DEGRADED_WARNING]
    assert second_run.module_results.technical is not None
    assert second_run.module_results.technical.status == ModuleExecutionStatus.DEGRADED

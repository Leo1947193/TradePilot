from __future__ import annotations

from app.graph.nodes.run_event import (
    EVENT_DEGRADED_REASON,
    EVENT_DEGRADED_SUMMARY,
    EVENT_DEGRADED_WARNING,
    run_event,
)
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_event_writes_degraded_module_result() -> None:
    state = run_event(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.event is not None
    assert state.module_results.event.module == AnalysisModuleName.EVENT
    assert state.module_results.event.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.event.low_confidence is True
    assert state.module_results.event.summary == EVENT_DEGRADED_SUMMARY
    assert state.module_results.event.reason == EVENT_DEGRADED_REASON


def test_run_event_updates_diagnostics_without_duplicates() -> None:
    state = run_event(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["event"]
    assert state.diagnostics.warnings == [EVENT_DEGRADED_WARNING]


def test_run_event_preserves_unrelated_state() -> None:
    state = run_event(
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
                "excluded_modules": ["sentiment"],
                "warnings": ["existing warning"],
            },
        }
    )

    assert state.request_id == "req_789"
    assert state.context.market == "US"
    assert state.module_results.technical is not None
    assert state.module_results.technical.module == "technical"
    assert state.diagnostics.excluded_modules == ["sentiment"]
    assert state.diagnostics.warnings == ["existing warning", EVENT_DEGRADED_WARNING]


def test_run_event_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_event(initial_state)
    second_run = run_event(first_run)

    assert second_run.diagnostics.degraded_modules == ["event"]
    assert second_run.diagnostics.warnings == [EVENT_DEGRADED_WARNING]
    assert second_run.module_results.event is not None
    assert second_run.module_results.event.status == ModuleExecutionStatus.DEGRADED

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.graph.nodes.run_event import (
    EVENT_DEGRADED_REASON,
    EVENT_DEGRADED_SUMMARY,
    EVENT_DEGRADED_WARNING,
    EVENT_USABLE_SUMMARY,
    run_event,
)
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent, ProviderSourceRef
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


def test_run_event_uses_provider_data_when_available() -> None:
    source = ProviderSourceRef(
        name="provider-x",
        url="https://example.com/source",
        fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    class FakeCompanyEventsProvider:
        async def get_company_events(self, symbol: str, *, days_ahead: int) -> list[CompanyEvent]:
            return [
                CompanyEvent(
                    symbol=symbol,
                    event_type="earnings",
                    title="AAPL earnings",
                    scheduled_at=datetime(2026, 4, 20, 20, 30, tzinfo=UTC),
                    category="company",
                    source=source,
                )
            ]

    class FakeMacroCalendarProvider:
        async def get_macro_events(self, *, market: str, days_ahead: int) -> list[MacroCalendarEvent]:
            return [
                MacroCalendarEvent(
                    event_name="CPI",
                    country=market,
                    category="inflation",
                    scheduled_at=datetime(2026, 4, 18, 12, 30, tzinfo=UTC),
                    importance="high",
                    source=ProviderSourceRef(
                        name="macro-provider",
                        url="https://example.com/macro",
                        fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                    ),
                )
            ]

    state = run_event(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_provider",
            "context": {
                "market": "US",
                "analysis_window_days": [7, 90],
            },
        },
        company_events_provider=FakeCompanyEventsProvider(),
        macro_calendar_provider=FakeMacroCalendarProvider(),
    )

    assert state.module_results.event is not None
    assert state.module_results.event.status == ModuleExecutionStatus.USABLE
    assert state.module_results.event.summary == EVENT_USABLE_SUMMARY.format(
        company_count=1,
        macro_count=1,
    )
    assert [source.name for source in state.sources] == ["provider-x", "macro-provider"]
    assert state.diagnostics.degraded_modules == []
    assert state.diagnostics.warnings == []


def test_run_event_falls_back_to_degraded_when_provider_call_fails() -> None:
    class BrokenCompanyEventsProvider:
        async def get_company_events(self, symbol: str, *, days_ahead: int):
            raise RuntimeError("provider down")

    class FakeMacroCalendarProvider:
        async def get_macro_events(self, *, market: str, days_ahead: int) -> list[MacroCalendarEvent]:
            return []

    state = run_event(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_provider_error",
            "context": {
                "market": "US",
                "analysis_window_days": [7, 90],
            },
        },
        company_events_provider=BrokenCompanyEventsProvider(),
        macro_calendar_provider=FakeMacroCalendarProvider(),
    )

    assert state.module_results.event is not None
    assert state.module_results.event.status == ModuleExecutionStatus.DEGRADED
    assert state.diagnostics.degraded_modules == ["event"]
    assert state.diagnostics.warnings == [EVENT_DEGRADED_WARNING]

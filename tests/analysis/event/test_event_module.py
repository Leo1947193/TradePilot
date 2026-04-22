from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.event.module import analyze_event_aggregate, analyze_event_module
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent, ProviderSourceRef


def make_company_event() -> CompanyEvent:
    return CompanyEvent(
        symbol="AAPL",
        event_type="earnings",
        title="AAPL earnings",
        scheduled_at=datetime(2026, 4, 20, 20, 30, tzinfo=UTC),
        category="company",
        source=ProviderSourceRef(
            name="provider-x",
            url="https://example.com/source",
            fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        ),
    )


def make_macro_event() -> MacroCalendarEvent:
    return MacroCalendarEvent(
        event_name="CPI",
        country="US",
        category="macro",
        scheduled_at=datetime(2026, 4, 18, 12, 30, tzinfo=UTC),
        importance="high",
        source=ProviderSourceRef(
            name="macro-provider",
            url="https://example.com/macro",
            fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        ),
    )


def test_analyze_event_module_maps_aggregate_to_analysis_module_result() -> None:
    analysis_time = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    aggregate = analyze_event_aggregate([make_company_event()], [make_macro_event()], analysis_time=analysis_time)
    result = analyze_event_module([make_company_event()], [make_macro_event()], analysis_time=analysis_time)

    assert result.module == "event"
    assert result.status == "usable"
    assert result.direction == aggregate.subresults["legacy_signal"].direction
    assert result.summary == aggregate.subresults["legacy_signal"].summary
    assert result.data_completeness_pct == 100.0

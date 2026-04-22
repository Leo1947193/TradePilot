from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.event.aggregate import aggregate_event_signals
from app.analysis.event.company_catalysts import analyze_company_catalysts
from app.analysis.event.macro_sensitivity import analyze_macro_sensitivity
from app.analysis.event.scheduled_events import analyze_scheduled_events
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent, ProviderSourceRef


def make_company_event(*, event_type: str, title: str, scheduled_at: datetime) -> CompanyEvent:
    return CompanyEvent(
        symbol="AAPL",
        event_type=event_type,
        title=title,
        scheduled_at=scheduled_at,
        category="company",
        source=ProviderSourceRef(
            name="provider-x",
            url="https://example.com/source",
            fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        ),
    )


def make_macro_event(*, event_name: str, scheduled_at: datetime, importance: str) -> MacroCalendarEvent:
    return MacroCalendarEvent(
        event_name=event_name,
        country="US",
        category="macro",
        scheduled_at=scheduled_at,
        importance=importance,
        source=ProviderSourceRef(
            name="macro-provider",
            url="https://example.com/macro",
            fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        ),
    )


def test_aggregate_event_signals_surfaces_controlled_risk_flags() -> None:
    analysis_time = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    scheduled = analyze_scheduled_events(
        [make_company_event(event_type="earnings", title="AAPL earnings", scheduled_at=datetime(2026, 4, 20, 20, 30, tzinfo=UTC))],
        analysis_time=analysis_time,
    )
    macro = analyze_macro_sensitivity(
        [make_macro_event(event_name="CPI", scheduled_at=datetime(2026, 4, 18, 12, 30, tzinfo=UTC), importance="high")],
        analysis_time=analysis_time,
    )
    catalysts = analyze_company_catalysts([], analysis_time=analysis_time)

    aggregate = aggregate_event_signals(
        scheduled_events=scheduled,
        macro_sensitivity=macro,
        company_catalysts=catalysts,
    )

    assert aggregate.event_bias == "neutral"
    assert aggregate.event_risk_flags == [
        "earnings_within_3d",
        "binary_event_imminent",
        "macro_event_high_sensitivity",
    ]
    assert "AAPL earnings" in aggregate.risk_events
    assert "CPI" in aggregate.risk_events


def test_aggregate_event_signals_can_turn_bullish_on_confirmed_positive_catalyst() -> None:
    analysis_time = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    scheduled = analyze_scheduled_events([], analysis_time=analysis_time)
    macro = analyze_macro_sensitivity([], analysis_time=analysis_time)
    catalysts = analyze_company_catalysts(
        [make_company_event(event_type="launch", title="Vision product launch", scheduled_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC))],
        analysis_time=analysis_time,
    )

    aggregate = aggregate_event_signals(
        scheduled_events=scheduled,
        macro_sensitivity=macro,
        company_catalysts=catalysts,
    )

    assert aggregate.event_bias == "bullish"
    assert aggregate.upcoming_catalysts == ["Vision product launch"]

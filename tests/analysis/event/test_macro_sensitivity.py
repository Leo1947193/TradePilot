from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.event.macro_sensitivity import analyze_macro_sensitivity
from app.services.providers.dtos import MacroCalendarEvent, ProviderSourceRef


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


def test_analyze_macro_sensitivity_flags_high_importance_near_term_events() -> None:
    result = analyze_macro_sensitivity(
        [
            make_macro_event(
                event_name="CPI",
                scheduled_at=datetime(2026, 4, 18, 12, 30, tzinfo=UTC),
                importance="high",
            )
        ],
        analysis_time=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    assert result.event_risk_flags == ["macro_event_high_sensitivity"]
    assert result.risk_events == ["CPI"]
    assert result.macro_event_exposure == "high"

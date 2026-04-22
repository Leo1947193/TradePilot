from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.event.scheduled_events import analyze_scheduled_events
from app.services.providers.dtos import CompanyEvent, ProviderSourceRef


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


def test_analyze_scheduled_events_marks_earnings_within_three_days() -> None:
    result = analyze_scheduled_events(
        [
            make_company_event(
                event_type="earnings",
                title="AAPL earnings",
                scheduled_at=datetime(2026, 4, 20, 20, 30, tzinfo=UTC),
            )
        ],
        analysis_time=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    assert result.risk_events == ["AAPL earnings"]
    assert result.event_risk_flags == ["earnings_within_3d", "binary_event_imminent"]
    assert result.low_confidence is False


def test_analyze_scheduled_events_collects_positive_catalysts() -> None:
    result = analyze_scheduled_events(
        [
            make_company_event(
                event_type="launch",
                title="Vision product launch",
                scheduled_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
            )
        ],
        analysis_time=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    assert result.upcoming_catalysts == ["Vision product launch"]
    assert result.confirmed_positive_catalysts == 1

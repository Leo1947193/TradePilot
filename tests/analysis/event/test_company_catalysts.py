from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.event.company_catalysts import analyze_company_catalysts
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


def test_analyze_company_catalysts_tracks_regulatory_risk() -> None:
    result = analyze_company_catalysts(
        [
            make_company_event(
                event_type="regulatory_decision",
                title="EU regulatory decision",
                scheduled_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
            )
        ],
        analysis_time=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    assert result.risk_events == ["EU regulatory decision"]
    assert result.event_risk_flags == ["regulatory_decision_imminent"]


def test_analyze_company_catalysts_tracks_binary_events_without_direction_override() -> None:
    result = analyze_company_catalysts(
        [
            make_company_event(
                event_type="shareholder_vote",
                title="Merger vote",
                scheduled_at=datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
            )
        ],
        analysis_time=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )

    assert result.binary_event_count == 1
    assert result.event_risk_flags == ["binary_event_imminent"]

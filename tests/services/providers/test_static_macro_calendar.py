from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json

import pytest

from app.services.providers.static_macro_calendar import StaticMacroCalendarProvider


def write_calendar(tmp_path, payload: list[dict]) -> str:
    path = tmp_path / "macro_calendar.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_static_macro_calendar_provider_filters_and_sorts_events(tmp_path) -> None:
    path = write_calendar(
        tmp_path,
        [
            {
                "event_name": "CPI",
                "country": "US",
                "category": "inflation",
                "scheduled_at": "2026-04-19T12:30:00Z",
                "importance": "high",
            },
            {
                "event_name": "FOMC",
                "country": "US",
                "category": "rates",
                "scheduled_at": "2026-04-18T18:00:00Z",
                "importance": "high",
            },
            {
                "event_name": "ECB",
                "country": "EU",
                "category": "rates",
                "scheduled_at": "2026-04-18T11:00:00Z",
                "importance": "high",
            },
            {
                "event_name": "Old Event",
                "country": "US",
                "category": "rates",
                "scheduled_at": "2026-04-16T11:00:00Z",
                "importance": "low",
            },
        ],
    )
    provider = StaticMacroCalendarProvider(
        path,
        source_url="https://example.com/macro-calendar",
        now_provider=lambda: datetime(2026, 4, 17, 0, 0, tzinfo=UTC),
    )

    events = asyncio.run(provider.get_macro_events(market="us", days_ahead=3))

    assert [event.event_name for event in events] == ["FOMC", "CPI"]
    assert all(event.country == "US" for event in events)
    assert all(event.source.name == "static_macro_calendar" for event in events)
    assert str(events[0].source.url) == "https://example.com/macro-calendar"


def test_static_macro_calendar_provider_rejects_invalid_calendar_shape(tmp_path) -> None:
    path = tmp_path / "macro_calendar.json"
    path.write_text(json.dumps({"event_name": "CPI"}), encoding="utf-8")
    provider = StaticMacroCalendarProvider(
        path,
        now_provider=lambda: datetime(2026, 4, 17, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="JSON array"):
        asyncio.run(provider.get_macro_events(market="US", days_ahead=7))


def test_static_macro_calendar_provider_requires_utc_now_provider(tmp_path) -> None:
    path = write_calendar(
        tmp_path,
        [
            {
                "event_name": "CPI",
                "country": "US",
                "category": "inflation",
                "scheduled_at": "2026-04-19T12:30:00Z",
            }
        ],
    )
    provider = StaticMacroCalendarProvider(
        path,
        now_provider=lambda: datetime(2026, 4, 17, 0, 0),
    )

    with pytest.raises(ValueError, match="UTC-aware datetime"):
        asyncio.run(provider.get_macro_events(market="US", days_ahead=7))

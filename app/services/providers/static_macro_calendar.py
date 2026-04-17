from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import json
from typing import Callable

from app.services.providers.dtos import MacroCalendarEvent, ProviderSourceRef


class StaticMacroCalendarProvider:
    def __init__(
        self,
        calendar_path: str | Path,
        *,
        source_name: str = "static_macro_calendar",
        source_url: str | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._calendar_path = Path(calendar_path)
        self._source_name = source_name
        self._source_url = source_url
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def get_macro_events(self, *, market: str, days_ahead: int) -> list[MacroCalendarEvent]:
        now = self._now_provider()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("now_provider must return a UTC-aware datetime")

        cutoff = now + timedelta(days=days_ahead)
        market_code = market.strip().upper()
        events: list[MacroCalendarEvent] = []

        for item in self._load_calendar_items():
            event = MacroCalendarEvent.model_validate(
                {
                    "event_name": item["event_name"],
                    "country": item["country"],
                    "category": item["category"],
                    "scheduled_at": item["scheduled_at"],
                    "importance": item.get("importance"),
                    "source": {
                        "name": self._source_name,
                        "url": self._source_url,
                        "fetched_at": now,
                    },
                }
            )
            if event.country.upper() != market_code:
                continue
            if event.scheduled_at < now or event.scheduled_at > cutoff:
                continue
            events.append(event)

        return sorted(events, key=lambda event: event.scheduled_at)

    def _load_calendar_items(self) -> list[dict]:
        text = self._calendar_path.read_text(encoding="utf-8")
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("static macro calendar file must contain a JSON array")

        items: list[dict] = []
        for entry in payload:
            if not isinstance(entry, dict):
                raise ValueError("static macro calendar entries must be JSON objects")
            items.append(entry)

        return items

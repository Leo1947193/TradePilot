from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from app.analysis.event.schemas import (
    EventSourceTraceEntry,
    MacroSensitivityEvent,
    MacroSensitivityResult,
)
from app.services.providers.dtos import MacroCalendarEvent

_HIGH_IMPORTANCE = {"high"}
_MEDIUM_IMPORTANCE = {"medium", "moderate"}
_HIGH_SENSITIVITY_TAGS = {
    "rates",
    "rate_sensitive",
    "duration",
    "growth",
    "macro_sensitive",
    "semiconductor",
    "export_controls",
    "housing",
    "consumer",
}


def analyze_macro_sensitivity(
    macro_events_or_payload: list[MacroCalendarEvent] | Mapping[str, Any],
    *,
    analysis_time: datetime | None = None,
    holding_horizon_days: int = 90,
    macro_sensitivity_context: Mapping[str, Any] | None = None,
) -> MacroSensitivityResult:
    payload = _coerce_payload(
        macro_events_or_payload,
        analysis_time=analysis_time,
        holding_horizon_days=holding_horizon_days,
        macro_sensitivity_context=macro_sensitivity_context,
    )

    resolved_analysis_time = payload["analysis_time"]
    resolved_horizon = payload["holding_horizon_days"]
    sensitivity_level = _resolve_sensitivity_level(
        payload.get("macro_sensitivity_context"),
        fallback_high=payload.get("_fallback_high_sensitivity", False),
    )

    records: list[MacroSensitivityEvent] = []
    risk_events: list[str] = []
    event_risk_flags: list[str] = []

    for raw_event in payload["macro_events"]:
        event_name = str(raw_event.get("event_name") or "").strip()
        category = str(raw_event.get("category") or "macro").strip().lower()
        scheduled_at = raw_event.get("scheduled_at")
        if not event_name or not isinstance(scheduled_at, datetime):
            continue

        days_until = (scheduled_at - resolved_analysis_time).total_seconds() / 86400
        if days_until < 0 or days_until > resolved_horizon:
            continue

        importance = _normalize_importance(raw_event.get("importance"))
        high_sensitivity = (
            sensitivity_level == "high"
            and 0 <= days_until <= 7
            and importance == "high"
        )
        if high_sensitivity:
            risk_events.append(event_name)
            event_risk_flags.append("macro_event_high_sensitivity")

        records.append(
            MacroSensitivityEvent(
                event_name=event_name,
                category=category,
                scheduled_at=scheduled_at,
                importance=importance,
                days_until=days_until,
                high_sensitivity=high_sensitivity,
                source_trace=(
                    _build_source_trace(raw_event, analysis_time=resolved_analysis_time),
                ),
            )
        )

    records.sort(key=lambda item: (item.days_until, -_importance_rank(item.importance), item.event_name))

    return MacroSensitivityResult(
        risk_events=_dedupe(risk_events),
        event_risk_flags=_dedupe(event_risk_flags),
        macro_event_exposure=_resolve_macro_event_exposure(
            records=records,
            sensitivity_level=sensitivity_level,
        ),
        data_completeness_pct=100.0 if records else 0.0,
        low_confidence=_resolve_low_confidence(
            records=records,
            sensitivity_level=sensitivity_level,
            used_context=payload.get("_used_context", False),
        ),
        records=tuple(records),
    )


def _coerce_payload(
    macro_events_or_payload: list[MacroCalendarEvent] | Mapping[str, Any],
    *,
    analysis_time: datetime | None,
    holding_horizon_days: int,
    macro_sensitivity_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(macro_events_or_payload, Mapping):
        payload = dict(macro_events_or_payload)
        resolved_analysis_time = payload.get("analysis_time")
        if not isinstance(resolved_analysis_time, datetime):
            raise ValueError("analysis_time is required")
        return {
            "analysis_time": resolved_analysis_time,
            "holding_horizon_days": int(payload.get("holding_horizon_days") or holding_horizon_days),
            "macro_sensitivity_context": payload.get("macro_sensitivity_context"),
            "macro_events": [dict(record) for record in payload.get("macro_events", ())],
            "_used_context": "macro_sensitivity_context" in payload,
            "_fallback_high_sensitivity": False,
        }

    if analysis_time is None:
        raise ValueError("analysis_time is required when passing macro event DTOs directly")

    return {
        "analysis_time": analysis_time,
        "holding_horizon_days": holding_horizon_days,
        "macro_sensitivity_context": dict(macro_sensitivity_context or {}),
        "macro_events": [
            {
                "event_name": event.event_name,
                "category": event.category,
                "scheduled_at": event.scheduled_at,
                "importance": event.importance,
                "source": {
                    "name": event.source.name,
                    "url": event.source.url,
                    "fetched_at": event.source.fetched_at,
                },
            }
            for event in macro_events_or_payload
        ],
        "_used_context": macro_sensitivity_context is not None,
        "_fallback_high_sensitivity": macro_sensitivity_context is None,
    }


def _resolve_sensitivity_level(context: Mapping[str, Any] | None, *, fallback_high: bool) -> str:
    if isinstance(context, Mapping):
        explicit = str(context.get("sensitivity_level") or "").strip().lower()
        if explicit in {"high", "medium", "low"}:
            return explicit

        if context.get("high_sensitivity") is True:
            return "high"
        if context.get("high_sensitivity") is False:
            return "low"

        tags = {
            str(tag).strip().lower()
            for tag in _flatten_tags(
                context.get("style_tags"),
                context.get("factor_tags"),
                context.get("industry_tags"),
            )
            if str(tag).strip()
        }
        if tags & _HIGH_SENSITIVITY_TAGS:
            return "high"
        if tags:
            return "medium"

    return "high" if fallback_high else "unknown"


def _flatten_tags(*tag_sets: Any) -> Iterable[Any]:
    for tag_set in tag_sets:
        if isinstance(tag_set, Iterable) and not isinstance(tag_set, (str, bytes)):
            yield from tag_set


def _normalize_importance(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in _HIGH_IMPORTANCE:
        return "high"
    if text in _MEDIUM_IMPORTANCE:
        return "medium"
    if text == "low":
        return "low"
    return None


def _importance_rank(value: str | None) -> int:
    return {"high": 3, "medium": 2, "low": 1, None: 0}[value]


def _resolve_macro_event_exposure(
    *,
    records: list[MacroSensitivityEvent],
    sensitivity_level: str,
) -> str:
    if not records:
        return "none"

    high_importance_count = sum(1 for record in records if record.importance == "high")
    if sensitivity_level == "high" and high_importance_count:
        return "high"
    if high_importance_count or sensitivity_level == "medium":
        return "moderate"
    return "low"


def _resolve_low_confidence(
    *,
    records: list[MacroSensitivityEvent],
    sensitivity_level: str,
    used_context: bool,
) -> bool:
    if not records:
        return True
    if not used_context and sensitivity_level == "high":
        return False
    return sensitivity_level == "unknown"


def _build_source_trace(raw_event: Mapping[str, Any], *, analysis_time: datetime) -> EventSourceTraceEntry:
    source = raw_event.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("macro event source is required")

    fetched_at = source.get("fetched_at")
    if not isinstance(fetched_at, datetime):
        raise ValueError("macro event source fetched_at is required")

    staleness_days = max((analysis_time.date() - fetched_at.date()).days, 0)
    return EventSourceTraceEntry(
        dataset="macro_events",
        source=str(source.get("name") or "unknown"),
        source_url=source.get("url"),
        fetched_at=fetched_at,
        staleness_days=staleness_days,
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped

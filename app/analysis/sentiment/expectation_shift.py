from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from statistics import median
from typing import Any

from app.analysis.sentiment.schemas import ExpectationShiftResult, NormalizedSentimentDataset
from app.schemas.modules import AnalysisDirection

POSITIVE_PROXY_TAGS = {"guidance_raise", "demand_improving", "execution_improving"}
NEGATIVE_PROXY_TAGS = {"guidance_cut", "demand_softening", "margin_pressure"}
POSITIVE_RATINGS = {"buy", "overweight", "outperform", "positive", "add"}
NEGATIVE_RATINGS = {"sell", "underweight", "underperform", "negative", "reduce"}

_UPGRADE_PATTERNS = ("upgrade", "raised to", "raises target", "target raised")
_DOWNGRADE_PATTERNS = ("downgrade", "cut to", "cuts target", "target cut")
_REITERATE_PATTERNS = ("reiterate", "maintain", "maintains", "keeps", "reaffirm")
_POSITIVE_PROXY_PATTERNS = (
    "guidance raised",
    "raises guidance",
    "demand improving",
    "demand improves",
    "execution improving",
)
_NEGATIVE_PROXY_PATTERNS = (
    "guidance cut",
    "cuts guidance",
    "demand softening",
    "margin pressure",
    "pressure on margins",
)
_TARGET_REVISION_PATTERN = re.compile(
    r"target(?: price)?(?: raised| cut| lowered)?\s+(?:to\s+)?\$?(?P<new>\d+(?:\.\d+)?)\s+from\s+\$?(?P<old>\d+(?:\.\d+)?)"
)


def analyze_expectation_shift(
    dataset_or_payload: NormalizedSentimentDataset | Mapping[str, Any],
) -> ExpectationShiftResult:
    payload = _coerce_payload(dataset_or_payload)
    analysis_time = payload["analysis_time"]

    deduped_actions = _dedupe_records(
        payload["analyst_actions"],
        dedupe_key=_action_dedupe_key,
        completeness_key=_action_completeness_key,
    )
    deduped_proxy_events = _dedupe_records(
        payload["expectation_proxy_events"],
        dedupe_key=_proxy_dedupe_key,
        completeness_key=_proxy_completeness_key,
    )

    recent_actions = [
        action
        for action in deduped_actions
        if _within_days(action.get("published_at"), analysis_time=analysis_time, days=30)
    ]
    recent_proxy_events = [
        event
        for event in deduped_proxy_events
        if _within_days(event.get("published_at"), analysis_time=analysis_time, days=14)
        and _coerce_float(event.get("relevance_score"), default=1.0) >= 0.60
        and _non_empty_text(event.get("headline"))
        and _non_empty_text(event.get("url"))
    ]

    positive_actions = 0
    negative_actions = 0
    neutral_actions = 0
    target_revisions: list[float] = []
    latest_action_by_firm_day: dict[tuple[str, str], dict[str, Any]] = {}
    for action in recent_actions:
        action_class = _classify_action(action)
        if action_class == "positive":
            positive_actions += 1
        elif action_class == "negative":
            negative_actions += 1
        else:
            neutral_actions += 1

        revision_candidate = _extract_target_revision(action)
        if revision_candidate is None:
            continue
        firm_key = (str(action.get("analyst_firm") or "unknown").strip().lower(), _date_key(action))
        existing_revision = latest_action_by_firm_day.get(firm_key)
        if existing_revision is None or _sort_timestamp(action.get("published_at")) >= _sort_timestamp(
            existing_revision.get("published_at")
        ):
            latest_action_by_firm_day[firm_key] = {**action, "_target_revision_pct": revision_candidate}

    target_revisions = [
        _coerce_float(action["_target_revision_pct"], default=0.0)
        for action in latest_action_by_firm_day.values()
    ]

    positive_proxy_count = 0
    negative_proxy_count = 0
    for event in recent_proxy_events:
        tag = str(event.get("tag") or "").strip().lower()
        if tag in POSITIVE_PROXY_TAGS:
            positive_proxy_count += 1
        elif tag in NEGATIVE_PROXY_TAGS:
            negative_proxy_count += 1

    valid_action_count = positive_actions + negative_actions + neutral_actions
    valid_proxy_count = positive_proxy_count + negative_proxy_count
    analyst_action_balance = round(
        (positive_actions - negative_actions) / max(valid_action_count, 1),
        2,
    )
    expectation_headline_balance = round(
        (positive_proxy_count - negative_proxy_count) / max(valid_proxy_count, 1),
        2,
    )
    target_revision_median = round(median(target_revisions), 2) if target_revisions else 0.0

    expectation_shift, direction = _resolve_expectation_shift(
        analyst_action_balance=analyst_action_balance,
        target_revision_median_pct_30d=target_revision_median,
        expectation_headline_balance_14d=expectation_headline_balance,
    )
    expectation_score = _resolve_expectation_score(
        analyst_action_balance=analyst_action_balance,
        target_revision_median_pct_30d=target_revision_median,
        expectation_headline_balance_14d=expectation_headline_balance,
    )

    low_confidence = valid_action_count < 2 or valid_proxy_count < 3
    data_completeness_pct = round(
        ((min(valid_action_count, 4) + min(valid_proxy_count, 4)) / 8) * 100,
        2,
    )
    attention_level = _estimate_attention_level(valid_proxy_count)

    summary = (
        "Expectation shift is "
        f"{expectation_shift} with score {expectation_score:.2f}; "
        f"analyst balance {analyst_action_balance:.2f}, "
        f"target revision median {target_revision_median:.2f}%, "
        f"expectation headline balance {expectation_headline_balance:.2f}, "
        f"attention {attention_level}."
    )

    return ExpectationShiftResult(
        direction=direction,
        expectation_shift=expectation_shift,
        expectation_score=expectation_score,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )


def _coerce_payload(dataset_or_payload: NormalizedSentimentDataset | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(dataset_or_payload, NormalizedSentimentDataset):
        derived_actions: list[dict[str, Any]] = []
        derived_proxy_events: list[dict[str, Any]] = []
        for item in dataset_or_payload.items:
            text = item.combined_text.lower()
            published_at = item.published_at
            action = _derive_action_from_text(item, text=text)
            if action is not None:
                derived_actions.append(action)
            tag = _derive_proxy_tag(text)
            if tag is not None:
                derived_proxy_events.append(
                    {
                        "event_id": item.dedupe_cluster_id,
                        "published_at": published_at,
                        "headline": item.title,
                        "tag": tag,
                        "relevance_score": 1.0,
                        "url": str(item.source_url),
                        "classifier_version": item.classifier_version,
                        "fetched_at": item.source_trace[0].fetched_at if item.source_trace else published_at,
                    }
                )

        analysis_time = max((item.published_at for item in dataset_or_payload.items), default=datetime.min.replace(tzinfo=None))
        return {
            "analysis_time": analysis_time,
            "analyst_actions": derived_actions,
            "expectation_proxy_events": derived_proxy_events,
        }

    payload = dict(dataset_or_payload)
    return {
        "analysis_time": payload.get("analysis_time") or datetime.min.replace(tzinfo=None),
        "analyst_actions": [dict(record) for record in payload.get("analyst_actions", ())],
        "expectation_proxy_events": [dict(record) for record in payload.get("expectation_proxy_events", ())],
    }


def _derive_action_from_text(item: Any, *, text: str) -> dict[str, Any] | None:
    if any(pattern in text for pattern in _UPGRADE_PATTERNS):
        rating_action = "upgrade"
    elif any(pattern in text for pattern in _DOWNGRADE_PATTERNS):
        rating_action = "downgrade"
    elif any(pattern in text for pattern in _REITERATE_PATTERNS):
        rating_action = "reiterate"
    else:
        return None

    revision = _extract_target_revision(
        {
            "headline": getattr(item, "title", ""),
            "summary": "",
        }
    )
    action: dict[str, Any] = {
        "action_id": getattr(item, "dedupe_cluster_id", None),
        "published_at": getattr(item, "published_at", None),
        "analyst_firm": getattr(item, "source_name", None),
        "rating_action": rating_action,
        "rating_after": None,
        "url": str(getattr(item, "source_url", "")),
        "fetched_at": getattr(item.source_trace[0], "fetched_at", getattr(item, "published_at", None))
        if getattr(item, "source_trace", ())
        else getattr(item, "published_at", None),
    }
    if revision is not None:
        match = _TARGET_REVISION_PATTERN.search(text)
        if match is not None:
            action["target_price_new"] = _coerce_float(match.group("new"), default=None)
            action["target_price_old"] = _coerce_float(match.group("old"), default=None)
            action["currency"] = "USD"
    return action


def _derive_proxy_tag(text: str) -> str | None:
    if any(pattern in text for pattern in _POSITIVE_PROXY_PATTERNS):
        return "guidance_raise"
    if any(pattern in text for pattern in _NEGATIVE_PROXY_PATTERNS):
        return "guidance_cut"
    return None


def _dedupe_records(
    records: Iterable[dict[str, Any]],
    *,
    dedupe_key: Any,
    completeness_key: Any,
) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for record in records:
        key = dedupe_key(record)
        existing = chosen.get(key)
        if existing is None or completeness_key(record) > completeness_key(existing):
            chosen[key] = record
    return list(chosen.values())


def _action_dedupe_key(record: Mapping[str, Any]) -> str:
    if _non_empty_text(record.get("action_id")):
        return f"action_id:{str(record['action_id']).strip()}"
    if _non_empty_text(record.get("analyst_firm")) or _non_empty_text(record.get("analyst_name")):
        return ":".join(
            [
                "firm_day",
                str(record.get("analyst_firm") or "").strip().lower(),
                str(record.get("analyst_name") or "").strip().lower(),
                _date_key(record),
                str(record.get("rating_action") or "").strip().lower(),
            ]
        )
    if _non_empty_text(record.get("url")):
        return f"url:{str(record['url']).strip().lower()}"
    return f"fallback:{_date_key(record)}:{str(record.get('headline') or '')}"


def _proxy_dedupe_key(record: Mapping[str, Any]) -> str:
    if _non_empty_text(record.get("event_id")):
        return f"event_id:{str(record['event_id']).strip()}"
    if _non_empty_text(record.get("url")):
        return f"url:{str(record['url']).strip().lower()}"
    return f"headline:{str(record.get('headline') or '').strip().lower()}:{_date_key(record)}"


def _action_completeness_key(record: Mapping[str, Any]) -> tuple[int, float, float]:
    completeness = sum(
        1
        for field in ("rating_after", "target_price_old", "target_price_new", "currency")
        if record.get(field) not in (None, "")
    )
    return (
        completeness,
        _sort_timestamp(record.get("published_at")),
        _sort_timestamp(record.get("fetched_at")),
    )


def _proxy_completeness_key(record: Mapping[str, Any]) -> tuple[int, str, float]:
    completeness = sum(
        1
        for field in ("headline", "summary", "tag", "url", "classifier_version")
        if record.get(field) not in (None, "")
    )
    return (
        completeness,
        str(record.get("classifier_version") or ""),
        _sort_timestamp(record.get("fetched_at")),
    )


def _classify_action(action: Mapping[str, Any]) -> str:
    rating_action = str(action.get("rating_action") or "").strip().lower()
    rating_after = str(action.get("rating_after") or "").strip().lower()

    if rating_action == "upgrade":
        return "positive"
    if rating_action == "downgrade":
        return "negative"
    if rating_action == "initiate":
        if rating_after in POSITIVE_RATINGS:
            return "positive"
        if rating_after in NEGATIVE_RATINGS:
            return "negative"
    return "neutral"


def _extract_target_revision(action: Mapping[str, Any]) -> float | None:
    target_price_old = _coerce_float(action.get("target_price_old"), default=None)
    target_price_new = _coerce_float(action.get("target_price_new"), default=None)
    currency = action.get("currency")

    if target_price_old is None or target_price_new is None:
        text = " ".join(
            str(action.get(field) or "") for field in ("headline", "summary")
        ).lower()
        match = _TARGET_REVISION_PATTERN.search(text)
        if match is None:
            return None
        target_price_new = _coerce_float(match.group("new"), default=None)
        target_price_old = _coerce_float(match.group("old"), default=None)
        currency = currency or "USD"

    if target_price_old is None or target_price_new is None or target_price_old <= 0 or not currency:
        return None

    revision_pct = ((target_price_new - target_price_old) / max(abs(target_price_old), 0.01)) * 100
    return round(max(-80.0, min(200.0, revision_pct)), 2)


def _resolve_expectation_shift(
    *,
    analyst_action_balance: float,
    target_revision_median_pct_30d: float,
    expectation_headline_balance_14d: float,
) -> tuple[str, AnalysisDirection]:
    if (
        analyst_action_balance <= -0.20
        or expectation_headline_balance_14d <= -0.25
        or target_revision_median_pct_30d <= -5.0
    ):
        return "deteriorating", AnalysisDirection.BEARISH
    if (
        analyst_action_balance >= 0.20
        or expectation_headline_balance_14d >= 0.25
        or target_revision_median_pct_30d >= 5.0
    ):
        return "improving", AnalysisDirection.BULLISH
    return "stable", AnalysisDirection.NEUTRAL


def _resolve_expectation_score(
    *,
    analyst_action_balance: float,
    target_revision_median_pct_30d: float,
    expectation_headline_balance_14d: float,
) -> float:
    normalized_revision = max(-1.0, min(1.0, target_revision_median_pct_30d / 20.0))
    weighted = (
        analyst_action_balance * 0.45
        + expectation_headline_balance_14d * 0.35
        + normalized_revision * 0.20
    )
    return round(max(0.0, min(100.0, 50.0 + weighted * 50.0)), 2)


def _estimate_attention_level(valid_proxy_count: int) -> str:
    if valid_proxy_count >= 6:
        return "High"
    if valid_proxy_count >= 3:
        return "Normal"
    return "Low"


def _within_days(value: Any, *, analysis_time: datetime, days: int) -> bool:
    if not isinstance(value, datetime):
        return False
    return analysis_time - timedelta(days=days) <= value <= analysis_time


def _date_key(record: Mapping[str, Any]) -> str:
    timestamp = record.get("published_at")
    if isinstance(timestamp, datetime):
        return timestamp.date().isoformat()
    return "unknown-date"


def _sort_timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return float("-inf")


def _coerce_float(value: Any, *, default: float | None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

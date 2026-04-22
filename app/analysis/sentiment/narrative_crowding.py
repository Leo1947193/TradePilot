from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from math import sqrt
from typing import Any

from app.analysis.sentiment.schemas import NarrativeCrowdingResult, NormalizedSentimentDataset
from app.schemas.modules import AnalysisDirection

_BULLISH_PATTERNS = (
    "beat",
    "beats",
    "strong",
    "growth",
    "improves",
    "improving",
    "accelerate",
    "accelerates",
    "approval",
    "contract win",
    "demand improving",
    "raises guidance",
)
_BEARISH_PATTERNS = (
    "downgrade",
    "cuts",
    "cut guidance",
    "lawsuit",
    "weak",
    "margin pressure",
    "delay",
    "recall",
)
_THEME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("demand_cycle", ("demand", "orders", "inventory", "sell-through", "growth")),
    ("product_execution", ("launch", "delivery", "ship", "production", "delay", "recall")),
    ("margin_cost", ("margin", "cost", "pricing", "profit", "gross margin")),
    ("capital_financing", ("cash", "financing", "buyback", "liquidity", "dilution")),
    ("regulation_policy", ("regulation", "approval", "investigation", "policy", "fda")),
    ("valuation_positioning", ("valuation", "positioning", "multiple", "crowded", "re-rating")),
)


def analyze_narrative_crowding(
    dataset_or_payload: NormalizedSentimentDataset | Mapping[str, Any],
) -> NarrativeCrowdingResult:
    payload = _coerce_payload(dataset_or_payload)
    analysis_time = payload["analysis_time"]
    records = _dedupe_records(payload["normalized_news_items"])

    directional_records = [
        record
        for record in records
        if _within_days(record.get("published_at"), analysis_time=analysis_time, days=14)
        and _coerce_float(record.get("relevance_score"), default=1.0) >= 0.60
        and _resolve_direction(record) != AnalysisDirection.NEUTRAL
    ]
    unique_sources_14d = {
        str(record.get("source_name") or "").strip().lower()
        for record in directional_records
        if str(record.get("source_name") or "").strip()
    }

    theme_stats: dict[tuple[str, AnalysisDirection], dict[str, Any]] = defaultdict(
        lambda: {
            "mention_count": 0,
            "sources": set(),
            "latest_published_at": None,
        }
    )
    for record in directional_records:
        direction = _resolve_direction(record)
        for theme in _extract_themes(record)[:2]:
            stats = theme_stats[(theme, direction)]
            stats["mention_count"] += 1
            stats["sources"].add(str(record.get("source_name") or "").strip().lower())
            published_at = record.get("published_at")
            if stats["latest_published_at"] is None or (
                isinstance(published_at, datetime) and published_at > stats["latest_published_at"]
            ):
                stats["latest_published_at"] = published_at

    bullish_active = _active_themes(theme_stats, AnalysisDirection.BULLISH)
    bearish_active = _active_themes(theme_stats, AnalysisDirection.BEARISH)
    bullish_sorted = _sort_active_themes(bullish_active)
    bearish_sorted = _sort_active_themes(bearish_active)

    total_directional_mentions = sum(item["mention_count"] for item in bullish_active + bearish_active)
    bullish_share = round(
        (bullish_sorted[0]["mention_count"] / max(total_directional_mentions, 1)) if bullish_sorted else 0.0,
        2,
    )
    bearish_share = round(
        (bearish_sorted[0]["mention_count"] / max(total_directional_mentions, 1)) if bearish_sorted else 0.0,
        2,
    )
    contradiction_ratio = round(
        min(len(bullish_active), len(bearish_active)) / max(len(bullish_active) + len(bearish_active), 1),
        2,
    )

    attention_zscore_7d, used_baseline_fallback = _attention_zscore_7d(
        mention_series=payload["mention_series"],
        analysis_time=analysis_time,
    )
    crowding_flag = (
        attention_zscore_7d >= 2.0
        and max(bullish_share, bearish_share) >= 0.35
        and contradiction_ratio < 0.30
    )

    insufficient_directional_evidence = len(directional_records) < 6 or len(unique_sources_14d) < 3
    narrative_state, direction = _resolve_narrative_state(
        bullish_share=bullish_share,
        bearish_share=bearish_share,
        contradiction_ratio=contradiction_ratio,
        insufficient_directional_evidence=insufficient_directional_evidence,
    )
    dominant_themes = [
        item["theme"] for item in (bullish_sorted[:3] if bullish_sorted else bearish_sorted[:3])
    ]
    dominant_narrative = ", ".join(dominant_themes) if dominant_themes else "limited_coverage"

    low_confidence = insufficient_directional_evidence or used_baseline_fallback
    data_completeness_pct = round(
        (
            min(len(directional_records), 6) / 6 * 60
            + min(len(unique_sources_14d), 3) / 3 * 20
            + (0 if used_baseline_fallback else 20)
        ),
        2,
    )
    narrative_score = _resolve_narrative_score(
        direction=direction,
        contradiction_ratio=contradiction_ratio,
        bullish_share=bullish_share,
        bearish_share=bearish_share,
        crowding_flag=crowding_flag,
    )

    baseline_note = " attention baseline fallback applied." if used_baseline_fallback else ""
    summary = (
        f"Narrative state is {narrative_state} with dominant narrative {dominant_narrative}; "
        f"bullish share {bullish_share:.2f}, bearish share {bearish_share:.2f}, "
        f"contradiction ratio {contradiction_ratio:.2f}, attention z-score {attention_zscore_7d:.2f}, "
        f"crowding {'on' if crowding_flag else 'off'}, narrative score {narrative_score:.2f}."
        f"{baseline_note}"
    )

    return NarrativeCrowdingResult(
        direction=direction,
        narrative_state=narrative_state,
        dominant_narrative=dominant_narrative,
        contradiction_ratio=contradiction_ratio,
        attention_zscore_7d=attention_zscore_7d,
        crowding_flag=crowding_flag,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )


def _coerce_payload(dataset_or_payload: NormalizedSentimentDataset | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(dataset_or_payload, NormalizedSentimentDataset):
        mention_counts = Counter(item.published_at.date() for item in dataset_or_payload.items)
        mention_series = [
            {
                "date": day,
                "mention_count": count,
                "unique_source_count": 1,
            }
            for day, count in sorted(mention_counts.items())
        ]
        analysis_time = max((item.published_at for item in dataset_or_payload.items), default=datetime.min.replace(tzinfo=None))
        return {
            "analysis_time": analysis_time,
            "normalized_news_items": [
                {
                    "headline": item.title,
                    "summary": "",
                    "published_at": item.published_at,
                    "source_name": item.source_name,
                    "source_type": "news",
                    "url": str(item.source_url),
                    "relevance_score": 1.0,
                    "canonical_headline": item.canonical_headline,
                    "combined_text": item.combined_text,
                }
                for item in dataset_or_payload.items
            ],
            "mention_series": mention_series,
        }

    payload = dict(dataset_or_payload)
    return {
        "analysis_time": payload.get("analysis_time") or datetime.min.replace(tzinfo=None),
        "normalized_news_items": [dict(item) for item in payload.get("normalized_news_items", ())],
        "mention_series": [dict(item) for item in payload.get("mention_series", ())],
    }


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for record in records:
        key = _dedupe_key(record)
        existing = chosen.get(key)
        if existing is None:
            chosen[key] = record
            continue
        if _record_sort_key(record) > _record_sort_key(existing):
            chosen[key] = record
    return list(chosen.values())


def _dedupe_key(record: Mapping[str, Any]) -> str:
    url = str(record.get("url") or "").strip().lower()
    if url:
        return f"url:{url}"
    return ":".join(
        [
            str(record.get("canonical_headline") or record.get("headline") or "").strip().lower(),
            str(record.get("source_name") or "").strip().lower(),
            _date_key(record.get("published_at")),
        ]
    )


def _record_sort_key(record: Mapping[str, Any]) -> tuple[int, float]:
    completeness = sum(
        1
        for field in ("headline", "summary", "url", "source_name", "published_at")
        if record.get(field) not in (None, "")
    )
    published_at = record.get("published_at")
    return (completeness, published_at.timestamp() if isinstance(published_at, datetime) else float("-inf"))


def _resolve_direction(record: Mapping[str, Any]) -> AnalysisDirection:
    explicit = str(record.get("direction") or record.get("sentiment_label") or record.get("news_tone") or "").strip().lower()
    if explicit in {"bullish", "positive"}:
        return AnalysisDirection.BULLISH
    if explicit in {"bearish", "negative"}:
        return AnalysisDirection.BEARISH

    text = str(record.get("combined_text") or "").lower()
    if not text:
        text = " ".join(str(record.get(field) or "") for field in ("headline", "summary")).lower()
    bullish_hits = sum(pattern in text for pattern in _BULLISH_PATTERNS)
    bearish_hits = sum(pattern in text for pattern in _BEARISH_PATTERNS)
    if bullish_hits > bearish_hits:
        return AnalysisDirection.BULLISH
    if bearish_hits > bullish_hits:
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL


def _extract_themes(record: Mapping[str, Any]) -> list[str]:
    text = str(record.get("combined_text") or "").lower()
    if not text:
        text = " ".join(str(record.get(field) or "") for field in ("headline", "summary")).lower()
    themes: list[str] = []
    for theme, keywords in _THEME_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            themes.append(theme)
    return themes


def _active_themes(
    theme_stats: Mapping[tuple[str, AnalysisDirection], Mapping[str, Any]],
    direction: AnalysisDirection,
) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for (theme, theme_direction), stats in theme_stats.items():
        if theme_direction != direction:
            continue
        if stats["mention_count"] < 2 or len(stats["sources"]) < 2:
            continue
        active.append(
            {
                "theme": theme,
                "mention_count": stats["mention_count"],
                "source_count": len(stats["sources"]),
                "latest_published_at": stats["latest_published_at"],
            }
        )
    return active


def _sort_active_themes(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        themes,
        key=lambda item: (
            item["mention_count"],
            item["source_count"],
            item["latest_published_at"].timestamp() if isinstance(item["latest_published_at"], datetime) else float("-inf"),
        ),
        reverse=True,
    )


def _resolve_narrative_state(
    *,
    bullish_share: float,
    bearish_share: float,
    contradiction_ratio: float,
    insufficient_directional_evidence: bool,
) -> tuple[str, AnalysisDirection]:
    if insufficient_directional_evidence or contradiction_ratio >= 0.45:
        return "mixed", AnalysisDirection.NEUTRAL
    if bullish_share > bearish_share:
        return "supportive", AnalysisDirection.BULLISH
    if bearish_share > bullish_share:
        return "fragile", AnalysisDirection.BEARISH
    return "mixed", AnalysisDirection.NEUTRAL


def _resolve_narrative_score(
    *,
    direction: AnalysisDirection,
    contradiction_ratio: float,
    bullish_share: float,
    bearish_share: float,
    crowding_flag: bool,
) -> float:
    direction_bias = bullish_share - bearish_share
    if direction == AnalysisDirection.BEARISH:
        direction_bias = bearish_share - bullish_share
    if direction == AnalysisDirection.NEUTRAL:
        base = 50.0
    else:
        base = 50.0 + direction_bias * 40.0
    penalty = contradiction_ratio * 20.0 + (10.0 if crowding_flag else 0.0)
    return round(max(0.0, min(100.0, base - penalty)), 2)


def _attention_zscore_7d(
    *,
    mention_series: list[dict[str, Any]],
    analysis_time: datetime,
) -> tuple[float, bool]:
    counts_by_day: dict[date, int] = {}
    for item in mention_series:
        day = item.get("date")
        if not isinstance(day, date):
            continue
        counts_by_day[day] = int(item.get("mention_count") or 0)

    current_end = analysis_time.date()
    current_window_days = [current_end - timedelta(days=offset) for offset in range(6, -1, -1)]
    current_mentions = sum(counts_by_day.get(day, 0) for day in current_window_days)

    baseline_end = current_end - timedelta(days=7)
    baseline_start = current_end - timedelta(days=96)
    rolling_values: list[int] = []
    day = baseline_start + timedelta(days=6)
    while day <= baseline_end:
        window_days = [day - timedelta(days=offset) for offset in range(6, -1, -1)]
        rolling_values.append(sum(counts_by_day.get(window_day, 0) for window_day in window_days))
        day += timedelta(days=1)

    if len(rolling_values) < 30:
        return 0.0, True

    mean = sum(rolling_values) / len(rolling_values)
    variance = sum((value - mean) ** 2 for value in rolling_values) / len(rolling_values)
    std = sqrt(variance)
    if std == 0:
        return 0.0, True
    return round((current_mentions - mean) / std, 2), False


def _within_days(value: Any, *, analysis_time: datetime, days: int) -> bool:
    if not isinstance(value, datetime):
        return False
    return analysis_time - timedelta(days=days) <= value <= analysis_time


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_key(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return "unknown-date"

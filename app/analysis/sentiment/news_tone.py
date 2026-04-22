from __future__ import annotations

import re

from app.analysis.sentiment.normalize import filter_relevant_news_items
from app.analysis.sentiment.schemas import NewsToneResult, NormalizedSentimentDataset, SourceTraceEntry
from app.schemas.modules import AnalysisDirection

BULLISH_TERMS = (
    "beat",
    "beats",
    "bullish",
    "expands",
    "gain",
    "growth",
    "raises",
    "rally",
    "strong",
    "upgrade",
)
BEARISH_TERMS = (
    "bearish",
    "cuts",
    "decline",
    "delay",
    "drop",
    "downgrade",
    "lawsuit",
    "loss",
    "miss",
    "misses",
    "recall",
    "weak",
)


def analyze_news_tone(dataset: NormalizedSentimentDataset) -> NewsToneResult:
    relevant_items = filter_relevant_news_items(dataset.items)
    ranked_items = sorted(
        relevant_items,
        key=lambda item: (
            item.published_at,
            item.canonical_headline,
            str(item.source_url),
        ),
        reverse=True,
    )[:5]

    bullish_hits = 0
    bearish_hits = 0
    weighted_signal = 0.0
    total_weight = 0.0
    source_trace: list[SourceTraceEntry] = []

    for position, item in enumerate(ranked_items):
        text = item.combined_text.lower()
        item_bullish_hits = _count_term_hits(text, BULLISH_TERMS)
        item_bearish_hits = _count_term_hits(text, BEARISH_TERMS)
        bullish_hits += item_bullish_hits
        bearish_hits += item_bearish_hits

        item_signal = _resolve_item_signal(item_bullish_hits, item_bearish_hits)
        weight = _recency_weight(position=position)
        weighted_signal += item_signal * weight
        total_weight += weight

        for trace in item.source_trace:
            if trace not in source_trace:
                source_trace.append(trace)

    recency_weighted_score = round(weighted_signal / max(total_weight, 0.01), 2)
    if recency_weighted_score > 0:
        direction = AnalysisDirection.BULLISH
        tone = "positive"
        bias_label = "bullish"
    elif recency_weighted_score < 0:
        direction = AnalysisDirection.BEARISH
        tone = "negative"
        bias_label = "bearish"
    else:
        direction = AnalysisDirection.NEUTRAL
        tone = "neutral"
        bias_label = "neutral"

    article_count = min(dataset.deduped_article_count, 5)
    data_completeness_pct = min(dataset.provider_article_count, 5) / 5 * 100
    low_confidence = article_count == 0 or (
        article_count < 2 and direction == AnalysisDirection.NEUTRAL
    )
    latest_headline = (
        ranked_items[0].canonical_headline
        if ranked_items
        else "No relevant headline retained"
    )
    summary = (
        f"Sentiment analysis reviewed {article_count} provider-backed news article"
        f"{'' if article_count == 1 else 's'} and found a {bias_label} bias "
        f"(bullish hits: {bullish_hits}, bearish hits: {bearish_hits}). "
        f"Latest headline: {latest_headline}"
    )
    classifier_version = (
        ranked_items[0].classifier_version if ranked_items else "sentiment-normalize-v1"
    )

    return NewsToneResult(
        direction=direction,
        news_tone=tone,
        bullish_hits=bullish_hits,
        bearish_hits=bearish_hits,
        recency_weighted_score=recency_weighted_score,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
        source_trace=tuple(source_trace),
        classifier_version=classifier_version,
    )


def _resolve_item_signal(bullish_hits: int, bearish_hits: int) -> int:
    if bullish_hits > bearish_hits:
        return 1
    if bearish_hits > bullish_hits:
        return -1
    return 0


def _recency_weight(*, position: int) -> float:
    if position == 0:
        return 1.0
    if position == 1:
        return 0.85
    if position in {2, 3}:
        return 0.65
    return 0.4


def _count_term_hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(term in text for term in terms)

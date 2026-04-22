from __future__ import annotations

import json
from datetime import UTC, datetime

from app.analysis.sentiment.aggregate import aggregate_sentiment_signals
from app.analysis.sentiment.news_tone import analyze_news_tone
from app.analysis.sentiment.schemas import (
    ExpectationShiftResult,
    NarrativeCrowdingResult,
    NormalizedNewsItem,
    NormalizedSentimentDataset,
    SourceTraceEntry,
)
from app.schemas.modules import AnalysisDirection


def _make_trace(index: int) -> SourceTraceEntry:
    return SourceTraceEntry(
        dataset="finnhub_news",
        source=f"source_{index}",
        source_url=f"https://example.com/source/{index}",
        article_url=f"https://example.com/article/{index}",
        fetched_at=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )


def _make_item(index: int, title: str, combined_text: str) -> NormalizedNewsItem:
    return NormalizedNewsItem(
        symbol="AAPL",
        title=title,
        canonical_headline=title,
        normalized_headline=title.lower(),
        combined_text=combined_text,
        published_at=datetime(2026, 4, 22, 12 - index, 0, tzinfo=UTC),
        source_name=f"Source {index}",
        source_url=f"https://example.com/source/{index}",
        category="company",
        dedupe_cluster_id=f"cluster-{index}",
        cluster_size=1,
        is_relevant=True,
        relevance_score=0.95,
        relevance_label="high",
        classifier_version="sentiment-normalize-v2",
        source_trace=(_make_trace(index),),
    )


def _make_dataset(*items: NormalizedNewsItem) -> NormalizedSentimentDataset:
    return NormalizedSentimentDataset(
        ticker="AAPL",
        provider_article_count=len(items),
        relevant_article_count=len(items),
        deduped_article_count=len(items),
        excluded_article_count=0,
        items=items,
    )


def test_aggregate_sentiment_signals_preserves_single_bullish_direction() -> None:
    dataset = _make_dataset(
        _make_item(
            0,
            "Apple beats expectations as services growth stays strong",
            "apple beats expectations as services growth stays strong",
        )
    )
    news_tone = analyze_news_tone(dataset)
    expectation_shift = ExpectationShiftResult(
        direction=AnalysisDirection.NEUTRAL,
        expectation_shift="Stable",
        expectation_score=0.0,
        summary="Expectation signals are stable.",
        data_completeness_pct=0.0,
        low_confidence=False,
    )
    narrative_crowding = NarrativeCrowdingResult(
        direction=AnalysisDirection.NEUTRAL,
        narrative_state="Mixed",
        dominant_narrative="balanced demand",
        contradiction_ratio=0.2,
        attention_zscore_7d=0.0,
        crowding_flag=False,
        summary="Narrative conditions are mixed.",
        data_completeness_pct=0.0,
        low_confidence=False,
    )

    aggregate = aggregate_sentiment_signals(
        dataset=dataset,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )
    weight_scheme = json.loads(aggregate.weight_scheme_used)

    assert aggregate.sentiment_bias == AnalysisDirection.BULLISH
    assert aggregate.news_tone == "positive"
    assert aggregate.data_completeness_pct == 20.0
    assert aggregate.low_confidence is False
    assert aggregate.key_risks == ["limited_news_coverage"]
    assert aggregate.market_expectation == (
        "Expectations are constructive with stable signals. Key risk: limited news coverage."
    )
    assert aggregate.summary == (
        "Sentiment bias is bullish; news tone is positive, expectation shift is stable, "
        "and narrative state is mixed."
    )
    assert weight_scheme["scheme"] == "sentiment_signal_aggregation_v1"
    assert weight_scheme["available_weight_sum"] == 1.0
    assert weight_scheme["renormalized"] is False


def test_aggregate_sentiment_signals_tracks_low_confidence_modules_and_conflicts() -> None:
    dataset = _make_dataset(
        _make_item(
            0,
            "Apple services growth remains solid",
            "apple services growth remains solid",
        ),
        _make_item(
            1,
            "Margin outlook mixed into next quarter",
            "margin outlook mixed into next quarter",
        ),
    )
    news_tone = analyze_news_tone(dataset)
    expectation_shift = ExpectationShiftResult(
        direction=AnalysisDirection.BEARISH,
        expectation_shift="Deteriorating",
        expectation_score=-0.8,
        summary="Estimate revisions turned lower.",
        data_completeness_pct=70.0,
        low_confidence=True,
    )
    narrative_crowding = NarrativeCrowdingResult(
        direction=AnalysisDirection.NEUTRAL,
        narrative_state="Mixed",
        dominant_narrative="AI optimism",
        contradiction_ratio=0.45,
        attention_zscore_7d=2.4,
        crowding_flag=True,
        summary="Crowding risk is elevated.",
        data_completeness_pct=65.0,
        low_confidence=True,
    )

    aggregate = aggregate_sentiment_signals(
        dataset=dataset,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )

    assert aggregate.sentiment_bias == AnalysisDirection.NEUTRAL
    assert aggregate.low_confidence is True
    assert aggregate.low_confidence_modules == ["expectation_shift", "narrative_crowding"]
    assert aggregate.key_risks == [
        "expectation_shift_low_confidence",
        "narrative_low_confidence",
        "crowded_narrative",
        "cross_signal_conflict",
    ]

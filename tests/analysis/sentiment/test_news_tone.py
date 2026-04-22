from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.sentiment.news_tone import analyze_news_tone
from app.analysis.sentiment.schemas import NormalizedNewsItem, NormalizedSentimentDataset, SourceTraceEntry
from app.schemas.modules import AnalysisDirection


def _make_trace(index: int) -> SourceTraceEntry:
    return SourceTraceEntry(
        dataset="finnhub_news",
        source=f"source_{index}",
        source_url=f"https://example.com/source/{index}",
        article_url=f"https://example.com/article/{index}",
        fetched_at=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )


def _make_item(
    *,
    index: int,
    title: str,
    combined_text: str,
) -> NormalizedNewsItem:
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


def test_analyze_news_tone_keeps_single_bullish_example_bullish() -> None:
    dataset = NormalizedSentimentDataset(
        ticker="AAPL",
        provider_article_count=1,
        relevant_article_count=1,
        deduped_article_count=1,
        excluded_article_count=0,
        items=(
            _make_item(
                index=0,
                title="Apple beats expectations as services growth stays strong",
                combined_text="apple beats expectations as services growth stays strong",
            ),
        ),
    )

    result = analyze_news_tone(dataset)

    assert result.direction == AnalysisDirection.BULLISH
    assert result.news_tone == "positive"
    assert result.data_completeness_pct == 20.0
    assert result.low_confidence is False
    assert result.recency_weighted_score == 1.0
    assert result.summary == (
        "Sentiment analysis reviewed 1 provider-backed news article and found a bullish bias "
        "(bullish hits: 4, bearish hits: 0). Latest headline: Apple beats expectations as "
        "services growth stays strong"
    )


def test_analyze_news_tone_caps_signal_window_at_five_articles() -> None:
    dataset = NormalizedSentimentDataset(
        ticker="AAPL",
        provider_article_count=7,
        relevant_article_count=6,
        deduped_article_count=6,
        excluded_article_count=1,
        items=tuple(
            _make_item(
                index=index,
                title=f"Headline {index}",
                combined_text=(
                    "constructive update with strong growth"
                    if index < 5
                    else "older bearish miss"
                ),
            )
            for index in range(6)
        ),
    )

    result = analyze_news_tone(dataset)

    assert result.direction == AnalysisDirection.BULLISH
    assert result.data_completeness_pct == 100.0
    assert result.recency_weighted_score == 1.0
    assert result.bullish_hits == 10
    assert result.bearish_hits == 0
    assert len(result.source_trace) == 5

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.sentiment.module import analyze_news_sentiment, analyze_sentiment_module
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus
from app.services.providers.dtos import NewsArticle, ProviderSourceRef


def make_news_article() -> NewsArticle:
    return NewsArticle(
        symbol="AAPL",
        title="Apple beats expectations as services growth stays strong",
        published_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        source_name="Example News",
        url="https://example.com/news/apple-steady",
        summary="Analysts highlight strong demand and another growth quarter.",
        category="company",
        source=ProviderSourceRef(
            name="finnhub",
            url="https://example.com/news/apple-steady",
            fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
        ),
    )


def test_analyze_news_sentiment_keeps_legacy_news_tone_summary_contract() -> None:
    result = analyze_news_sentiment([make_news_article()])

    assert result.direction == "bullish"
    assert result.summary == (
        "Sentiment analysis reviewed 1 provider-backed news article and found a bullish bias "
        "(bullish hits: 4, bearish hits: 0). Latest headline: Apple beats expectations as "
        "services growth stays strong"
    )
    assert result.data_completeness_pct == 20.0
    assert result.low_confidence is False


def test_analyze_sentiment_module_maps_richer_aggregate_without_recomputing() -> None:
    result = analyze_sentiment_module(
        {
            "sentiment_bias": "bearish",
            "data_completeness_pct": 72.5,
            "low_confidence_modules": ["expectation_shift"],
            "summary": "aggregate summary should not win",
            "subresults": {
                "news_tone": {
                    "summary": "news tone summary remains the public module summary",
                    "low_confidence": False,
                }
            },
        }
    )

    assert result.module == AnalysisModuleName.SENTIMENT
    assert result.status == ModuleExecutionStatus.USABLE
    assert result.direction == "bearish"
    assert result.summary == "news tone summary remains the public module summary"
    assert result.data_completeness_pct == 72.5
    assert result.low_confidence is False
    assert result.reason is None


def test_analyze_sentiment_module_falls_back_to_explicit_aggregate_fields() -> None:
    result = analyze_sentiment_module(
        {
            "sentiment_bias": "neutral",
            "status": "degraded",
            "data_completeness_pct": 45.0,
            "low_confidence": True,
            "sentiment_summary": "aggregate-provided sentiment summary",
        }
    )

    assert result.module == AnalysisModuleName.SENTIMENT
    assert result.status == ModuleExecutionStatus.DEGRADED
    assert result.direction == "neutral"
    assert result.summary == "aggregate-provided sentiment summary"
    assert result.data_completeness_pct == 45.0
    assert result.low_confidence is True

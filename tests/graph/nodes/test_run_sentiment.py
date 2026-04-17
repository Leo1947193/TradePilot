from __future__ import annotations

from datetime import UTC, datetime

from app.graph.nodes.run_sentiment import (
    SENTIMENT_DEGRADED_REASON,
    SENTIMENT_DEGRADED_SUMMARY,
    SENTIMENT_DEGRADED_WARNING,
    SENTIMENT_USABLE_SUMMARY,
    run_sentiment,
)
from app.services.providers.dtos import NewsArticle, ProviderSourceRef
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_sentiment_writes_degraded_module_result() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.sentiment is not None
    assert state.module_results.sentiment.module == AnalysisModuleName.SENTIMENT
    assert state.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.sentiment.low_confidence is True
    assert state.module_results.sentiment.summary == SENTIMENT_DEGRADED_SUMMARY
    assert state.module_results.sentiment.reason == SENTIMENT_DEGRADED_REASON


def test_run_sentiment_updates_diagnostics_without_duplicates() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["sentiment"]
    assert state.diagnostics.warnings == [SENTIMENT_DEGRADED_WARNING]


def test_run_sentiment_preserves_unrelated_state() -> None:
    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_789",
            "context": {
                "market": "US",
                "benchmark": "SPY",
                "analysis_window_days": [7, 90],
            },
            "module_results": {
                "technical": {
                    "status": "usable",
                    "summary": "Trend remains constructive.",
                    "direction": "bullish",
                    "data_completeness_pct": 95,
                }
            },
            "diagnostics": {
                "excluded_modules": ["event"],
                "warnings": ["existing warning"],
            },
        }
    )

    assert state.request_id == "req_789"
    assert state.context.market == "US"
    assert state.module_results.technical is not None
    assert state.module_results.technical.module == "technical"
    assert state.diagnostics.excluded_modules == ["event"]
    assert state.diagnostics.warnings == ["existing warning", SENTIMENT_DEGRADED_WARNING]


def test_run_sentiment_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_sentiment(initial_state)
    second_run = run_sentiment(first_run)

    assert second_run.diagnostics.degraded_modules == ["sentiment"]
    assert second_run.diagnostics.warnings == [SENTIMENT_DEGRADED_WARNING]
    assert second_run.module_results.sentiment is not None
    assert second_run.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED


class FakeNewsDataProvider:
    def __init__(
        self,
        articles: list[NewsArticle] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.articles = articles or []
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def get_company_news(self, symbol: str, *, limit: int) -> list[NewsArticle]:
        self.calls.append((symbol, limit))
        if self.error is not None:
            raise self.error
        return self.articles


def make_news_article() -> NewsArticle:
    return NewsArticle(
        symbol="AAPL",
        title="Apple holds steady ahead of earnings",
        published_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        source_name="Example News",
        url="https://example.com/news/apple-steady",
        summary="Apple shares trade in a narrow range before earnings.",
        category="company",
        source=ProviderSourceRef(
            name="finnhub",
            url="https://example.com/news/apple-steady",
            fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
        ),
    )


def test_run_sentiment_provider_backed_path_writes_usable_result() -> None:
    provider = FakeNewsDataProvider(articles=[make_news_article()])

    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_provider",
        },
        news_data_provider=provider,
    )

    assert provider.calls == [("AAPL", 5)]
    assert state.module_results.sentiment is not None
    assert state.module_results.sentiment.status == ModuleExecutionStatus.USABLE
    assert state.module_results.sentiment.direction == "neutral"
    assert state.module_results.sentiment.summary.startswith(SENTIMENT_USABLE_SUMMARY)
    assert "Latest headline: Apple holds steady ahead of earnings" in state.module_results.sentiment.summary
    assert state.module_results.sentiment.low_confidence is False
    assert state.diagnostics.degraded_modules == []
    assert state.diagnostics.warnings == []


def test_run_sentiment_provider_backed_path_appends_source_once() -> None:
    provider = FakeNewsDataProvider(articles=[make_news_article()])

    state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_source",
            "sources": [
                {
                    "type": "news",
                    "name": "finnhub",
                    "url": "https://example.com/news/apple-steady",
                }
            ],
        },
        news_data_provider=provider,
    )

    assert len(state.sources) == 1
    assert state.sources[0].name == "finnhub"


def test_run_sentiment_provider_errors_or_empty_articles_fall_back_to_degraded() -> None:
    empty_provider = FakeNewsDataProvider(articles=[])
    error_provider = FakeNewsDataProvider(error=RuntimeError("upstream failed"))

    empty_state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_empty",
        },
        news_data_provider=empty_provider,
    )
    error_state = run_sentiment(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_error",
        },
        news_data_provider=error_provider,
    )

    assert empty_state.module_results.sentiment is not None
    assert empty_state.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED
    assert error_state.module_results.sentiment is not None
    assert error_state.module_results.sentiment.status == ModuleExecutionStatus.DEGRADED

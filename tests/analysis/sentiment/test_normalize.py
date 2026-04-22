from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.sentiment.normalize import (
    DEFAULT_CLASSIFIER_VERSION,
    filter_relevant_news_items,
    normalize_news_articles,
)
from app.services.providers.dtos import NewsArticle, ProviderSourceRef


def make_news_article(
    *,
    title: str = "Apple beats expectations as services growth stays strong",
    published_at: datetime = datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    source_name: str = "Example News",
    url: str = "https://example.com/news/apple-steady",
    summary: str | None = "Analysts highlight strong demand and another growth quarter.",
    category: str | None = "company",
    provider_name: str = "finnhub",
    provider_url: str | None = "https://example.com/providers/finnhub",
    fetched_at: datetime = datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
) -> NewsArticle:
    return NewsArticle(
        symbol="AAPL",
        title=title,
        published_at=published_at,
        source_name=source_name,
        url=url,
        summary=summary,
        category=category,
        source=ProviderSourceRef(
            name=provider_name,
            url=provider_url,
            fetched_at=fetched_at,
        ),
    )


def test_normalize_news_articles_builds_canonical_item_with_trace_fields() -> None:
    dataset = normalize_news_articles([make_news_article()])

    assert len(dataset.items) == 1
    item = dataset.items[0]
    assert item.canonical_headline == "Apple beats expectations as services growth stays strong"
    assert item.normalized_headline == "apple beats expectations as services growth stays strong"
    assert item.classifier_version == DEFAULT_CLASSIFIER_VERSION
    assert item.is_relevant is True
    assert item.relevance_score == 0.8
    assert item.dedupe_cluster_id.startswith("AAPL-20260417-")
    assert item.cluster_size == 1
    assert len(item.source_trace) == 1
    assert item.source_trace[0].dataset == "news_items"
    assert item.source_trace[0].source == "finnhub"
    assert str(item.source_trace[0].source_url) == "https://example.com/providers/finnhub"
    assert str(item.source_trace[0].article_url) == "https://example.com/news/apple-steady"


def test_normalize_news_articles_deduplicates_cluster_and_keeps_richest_canonical_headline() -> None:
    dataset = normalize_news_articles(
        [
            make_news_article(
                title="Apple beats estimates",
                summary="Short summary.",
                url="https://example.com/news/dup-1",
                published_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                source_name="Wire One",
                provider_name="wire_one",
            ),
            make_news_article(
                title="Apple beats estimates!!!",
                summary="Longer duplicate summary with more context for later submodules.",
                url="https://example.com/news/dup-2",
                published_at=datetime(2026, 4, 17, 11, 0, tzinfo=UTC),
                source_name="Wire Two",
                provider_name="wire_two",
            ),
        ]
    )

    assert len(dataset.items) == 1
    item = dataset.items[0]
    assert item.canonical_headline == "Apple beats estimates!!!"
    assert item.normalized_headline == "apple beats estimates"
    assert item.cluster_size == 2
    assert len(item.source_trace) == 2
    assert [trace.source for trace in item.source_trace] == ["wire_one", "wire_two"]


def test_filter_relevant_news_items_filters_low_relevance_but_preserves_source_trace_in_normalized_output() -> None:
    dataset = normalize_news_articles(
        [
            make_news_article(
                title="Apple",
                summary=None,
                category=None,
                url="https://example.com/news/low-signal",
                provider_url=None,
            )
        ]
    )

    assert len(dataset.items) == 1
    assert dataset.items[0].is_relevant is False
    assert dataset.items[0].source_trace[0].missing_fields == ("summary", "category", "source_url")

    relevant_items = filter_relevant_news_items(dataset.items)

    assert relevant_items == ()

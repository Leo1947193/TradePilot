from __future__ import annotations

import re

from app.analysis.sentiment.schemas import (
    NormalizedNewsItem,
    NormalizedSentimentDataset,
    SourceTraceEntry,
)
from app.services.providers.dtos import NewsArticle

DEFAULT_CLASSIFIER_VERSION = "sentiment-normalize-v1"

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_news_articles(articles: list[NewsArticle]) -> NormalizedSentimentDataset:
    if not articles:
        return NormalizedSentimentDataset(
            ticker="UNKNOWN",
            provider_article_count=0,
            relevant_article_count=0,
            deduped_article_count=0,
            excluded_article_count=0,
            items=(),
        )

    ticker = articles[0].symbol
    normalized_items = [_normalize_article(article, ticker=ticker) for article in articles]
    deduped_items = _dedupe_items(normalized_items)
    relevant_item_count = sum(item.is_relevant for item in deduped_items)
    excluded_count = len(deduped_items) - relevant_item_count
    return NormalizedSentimentDataset(
        ticker=ticker,
        provider_article_count=len(articles),
        relevant_article_count=relevant_item_count,
        deduped_article_count=len(deduped_items),
        excluded_article_count=excluded_count,
        items=tuple(deduped_items),
    )


def filter_relevant_news_items(items: tuple[NormalizedNewsItem, ...]) -> tuple[NormalizedNewsItem, ...]:
    return tuple(item for item in items if item.is_relevant)


def _normalize_article(article: NewsArticle, *, ticker: str) -> NormalizedNewsItem:
    normalized_headline = _normalize_headline(article.title)
    missing_fields = _collect_missing_fields(article)
    relevance_score = _relevance_score(article, ticker=ticker, missing_fields=missing_fields)
    is_relevant = relevance_score >= 0.5
    return NormalizedNewsItem(
        symbol=article.symbol,
        title=article.title,
        canonical_headline=article.title,
        normalized_headline=normalized_headline,
        combined_text=" ".join(bit for bit in (article.title, article.summary, article.category) if bit).lower(),
        published_at=article.published_at,
        source_name=article.source_name,
        source_url=article.url,
        category=article.category,
        dedupe_cluster_id=f"{article.symbol}-{article.published_at:%Y%m%d}-{normalized_headline}",
        is_relevant=is_relevant,
        relevance_score=relevance_score,
        relevance_label="direct" if is_relevant else "weak",
        classifier_version=DEFAULT_CLASSIFIER_VERSION,
        source_trace=(
            SourceTraceEntry(
                dataset="news_items",
                source=article.source.name,
                source_url=article.source.url,
                article_url=article.url,
                fetched_at=article.source.fetched_at,
                missing_fields=missing_fields,
            ),
        ),
    )


def _dedupe_items(items: list[NormalizedNewsItem]) -> list[NormalizedNewsItem]:
    clusters: dict[str, list[NormalizedNewsItem]] = {}
    for item in sorted(items, key=lambda value: (value.published_at, len(value.combined_text)), reverse=True):
        cluster_key = item.dedupe_cluster_id
        clusters.setdefault(cluster_key, []).append(item)

    deduped_items: list[NormalizedNewsItem] = []
    for cluster in clusters.values():
        canonical_item = max(cluster, key=lambda value: (len(value.combined_text), len(value.title)))
        deduped_items.append(
            canonical_item.model_copy(
                update={
                    "cluster_size": len(cluster),
                    "source_trace": tuple(
                        trace
                        for item in cluster
                        for trace in item.source_trace
                    ),
                }
            )
        )

    return deduped_items


def _is_relevant(article: NewsArticle, *, ticker: str) -> bool:
    text = " ".join(bit for bit in (article.title, article.summary, article.category) if bit).lower()
    ticker_text = ticker.lower()
    return article.symbol.upper() == ticker.upper() or ticker_text in text


def _normalize_headline(title: str) -> str:
    normalized = _NON_ALNUM_PATTERN.sub(" ", title.lower()).strip()
    return " ".join(normalized.split())


def _collect_missing_fields(article: NewsArticle) -> tuple[str, ...]:
    missing_fields: list[str] = []
    if article.summary is None:
        missing_fields.append("summary")
    if article.category is None:
        missing_fields.append("category")
    if article.source.url is None:
        missing_fields.append("source_url")
    return tuple(missing_fields)


def _relevance_score(
    article: NewsArticle,
    *,
    ticker: str,
    missing_fields: tuple[str, ...],
) -> float:
    text = " ".join(bit for bit in (article.title, article.summary, article.category) if bit)
    if len(missing_fields) >= 2 or len(article.title.strip()) <= len(ticker) + 1:
        return 0.2
    if article.symbol.upper() == ticker.upper() and len(text.split()) >= 3:
        return 0.8
    if _is_relevant(article, ticker=ticker):
        return 0.6
    return 0.4

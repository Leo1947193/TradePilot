from __future__ import annotations

from dataclasses import dataclass

from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import NewsArticle


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


@dataclass(frozen=True)
class SentimentSignal:
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


def analyze_news_sentiment(articles: list[NewsArticle]) -> SentimentSignal:
    article_count = len(articles)
    bullish_hits = 0
    bearish_hits = 0

    for article in articles:
        text = " ".join(
            bit for bit in (article.title, article.summary, article.category) if bit
        ).lower()
        bullish_hits += sum(term in text for term in BULLISH_TERMS)
        bearish_hits += sum(term in text for term in BEARISH_TERMS)

    score = bullish_hits - bearish_hits
    if score > 0:
        direction = AnalysisDirection.BULLISH
        bias_label = "bullish"
    elif score < 0:
        direction = AnalysisDirection.BEARISH
        bias_label = "bearish"
    else:
        direction = AnalysisDirection.NEUTRAL
        bias_label = "neutral"

    data_completeness_pct = min(article_count, 5) / 5 * 100
    low_confidence = article_count < 2 and direction == AnalysisDirection.NEUTRAL
    latest_headline = articles[0].title

    summary = (
        f"Sentiment analysis reviewed {article_count} provider-backed news article"
        f"{'' if article_count == 1 else 's'} and found a {bias_label} bias "
        f"(bullish hits: {bullish_hits}, bearish hits: {bearish_hits}). "
        f"Latest headline: {latest_headline}"
    )

    return SentimentSignal(
        direction=direction,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.analysis.sentiment.aggregate import aggregate_sentiment_signals
from app.analysis.sentiment.expectation_shift import analyze_expectation_shift
from app.analysis.sentiment.narrative_crowding import analyze_narrative_crowding
from app.analysis.sentiment.news_tone import analyze_news_tone
from app.analysis.sentiment.normalize import normalize_news_articles
from app.analysis.sentiment.schemas import SentimentAggregateResult
from app.schemas.modules import (
    AnalysisDirection,
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.dtos import NewsArticle


def analyze_sentiment_module(
    aggregate_or_articles: SentimentAggregateResult | Mapping[str, Any] | Sequence[NewsArticle],
) -> AnalysisModuleResult:
    if _looks_like_aggregate(aggregate_or_articles):
        aggregate_result = aggregate_or_articles
    else:
        aggregate_result = analyze_sentiment_aggregate(list(aggregate_or_articles))

    direction = _coerce_direction(_get_value(aggregate_result, "sentiment_bias"))
    if direction is None:
        direction = _coerce_direction(_get_value(aggregate_result, "direction"))

    return AnalysisModuleResult(
        module=AnalysisModuleName.SENTIMENT,
        status=_coerce_status(_get_value(aggregate_result, "status")),
        summary=_resolve_module_summary(aggregate_result),
        direction=direction,
        data_completeness_pct=_get_value(aggregate_result, "data_completeness_pct"),
        low_confidence=_resolve_module_low_confidence(aggregate_result),
        reason=None,
    )


def analyze_sentiment_aggregate(articles: list[NewsArticle]) -> SentimentAggregateResult:
    dataset = normalize_news_articles(articles)
    news_tone = analyze_news_tone(dataset)
    expectation_shift = analyze_expectation_shift(dataset)
    narrative_crowding = analyze_narrative_crowding(dataset)
    return aggregate_sentiment_signals(
        dataset=dataset,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )


def analyze_news_sentiment(articles: list[NewsArticle]):
    aggregate_result = analyze_sentiment_aggregate(articles)
    return aggregate_result.subresults["news_tone"]


def _resolve_module_summary(aggregate_result: SentimentAggregateResult | Mapping[str, Any]) -> str:
    news_tone = _get_subresult(aggregate_result, "news_tone")
    if news_tone is None:
        summary = _get_value(aggregate_result, "sentiment_summary")
        if isinstance(summary, str) and summary:
            return summary
        fallback_summary = _get_value(aggregate_result, "summary")
        if isinstance(fallback_summary, str) and fallback_summary:
            return fallback_summary
        return ""

    summary = news_tone.get("summary") if isinstance(news_tone, Mapping) else getattr(news_tone, "summary", None)
    if isinstance(summary, str) and summary:
        return summary

    fallback_summary = _get_value(aggregate_result, "summary")
    if isinstance(fallback_summary, str):
        return fallback_summary
    return ""


def _resolve_module_low_confidence(aggregate_result: SentimentAggregateResult | Mapping[str, Any]) -> bool:
    news_tone = _get_subresult(aggregate_result, "news_tone")
    if news_tone is None:
        explicit_low_confidence = _get_value(aggregate_result, "low_confidence")
        if isinstance(explicit_low_confidence, bool):
            return explicit_low_confidence
        low_confidence_modules = _get_value(aggregate_result, "low_confidence_modules")
        return bool(low_confidence_modules)

    low_confidence = (
        news_tone.get("low_confidence") if isinstance(news_tone, Mapping) else getattr(news_tone, "low_confidence", None)
    )
    if isinstance(low_confidence, bool):
        return low_confidence

    explicit_low_confidence = _get_value(aggregate_result, "low_confidence")
    if isinstance(explicit_low_confidence, bool):
        return explicit_low_confidence
    return False


def _looks_like_aggregate(value: object) -> bool:
    if isinstance(value, SentimentAggregateResult):
        return True
    if isinstance(value, Mapping):
        return "sentiment_bias" in value or "subresults" in value or "sentiment_summary" in value
    return False


def _get_subresult(
    aggregate_result: SentimentAggregateResult | Mapping[str, Any],
    key: str,
) -> Any:
    subresults = _get_value(aggregate_result, "subresults")
    if isinstance(subresults, Mapping):
        return subresults.get(key)
    return None


def _get_value(aggregate_result: SentimentAggregateResult | Mapping[str, Any], key: str) -> Any:
    if isinstance(aggregate_result, Mapping):
        return aggregate_result.get(key)
    return getattr(aggregate_result, key, None)


def _coerce_direction(value: Any) -> AnalysisDirection | None:
    if isinstance(value, AnalysisDirection):
        return value
    if isinstance(value, str):
        try:
            return AnalysisDirection(value)
        except ValueError:
            return None
    return None


def _coerce_status(value: Any) -> ModuleExecutionStatus:
    if isinstance(value, ModuleExecutionStatus):
        return value
    if isinstance(value, str):
        try:
            return ModuleExecutionStatus(value)
        except ValueError:
            return ModuleExecutionStatus.USABLE
    return ModuleExecutionStatus.USABLE

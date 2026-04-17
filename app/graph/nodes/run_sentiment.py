from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, TypeVar

from app.analysis.sentiment import analyze_news_sentiment
from app.schemas.api import Source, SourceType
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import (
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.interfaces import NewsDataProvider


SENTIMENT_DEGRADED_SUMMARY = (
    "Sentiment analysis is degraded because provider-backed news data is not available yet."
)
SENTIMENT_DEGRADED_REASON = (
    "sentiment module placeholder until provider integration is implemented"
)
SENTIMENT_DEGRADED_WARNING = (
    "Sentiment analysis degraded: provider-backed news data is not available yet."
)

AwaitableT = TypeVar("AwaitableT")


def run_sentiment(
    state: TradePilotState | dict,
    news_data_provider: NewsDataProvider | None = None,
) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if news_data_provider is not None:
        provider_backed_state = _try_provider_backed_result(validated_state, news_data_provider)
        if provider_backed_state is not None:
            return provider_backed_state

    sentiment_result = AnalysisModuleResult(
        module=AnalysisModuleName.SENTIMENT,
        status=ModuleExecutionStatus.DEGRADED,
        summary=SENTIMENT_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=SENTIMENT_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.SENTIMENT.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.SENTIMENT.value)

    warnings = list(validated_state.diagnostics.warnings)
    if SENTIMENT_DEGRADED_WARNING not in warnings:
        warnings.append(SENTIMENT_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"sentiment": sentiment_result}
    )
    updated_diagnostics = validated_state.diagnostics.model_copy(
        update={
            "degraded_modules": degraded_modules,
            "warnings": warnings,
        }
    )

    return validated_state.model_copy(
        update={
            "module_results": updated_module_results,
            "diagnostics": updated_diagnostics,
        }
    )


def _try_provider_backed_result(
    validated_state: TradePilotState,
    news_data_provider: NewsDataProvider,
) -> TradePilotState | None:
    normalized_ticker = validated_state.normalized_ticker
    if normalized_ticker is None or not normalized_ticker.strip():
        return None

    try:
        articles = _run_awaitable(
            news_data_provider.get_company_news(normalized_ticker, limit=5)
        )
    except Exception:
        return None

    if not articles:
        return None

    sentiment_signal = analyze_news_sentiment(articles)

    sentiment_result = AnalysisModuleResult(
        module=AnalysisModuleName.SENTIMENT,
        status=ModuleExecutionStatus.USABLE,
        summary=sentiment_signal.summary,
        direction=sentiment_signal.direction,
        data_completeness_pct=sentiment_signal.data_completeness_pct,
        low_confidence=sentiment_signal.low_confidence,
        reason=None,
    )

    degraded_modules = [
        module_name
        for module_name in validated_state.diagnostics.degraded_modules
        if module_name != AnalysisModuleName.SENTIMENT.value
    ]
    warnings = [
        warning
        for warning in validated_state.diagnostics.warnings
        if warning != SENTIMENT_DEGRADED_WARNING
    ]

    updated_sources = list(validated_state.sources)
    first_article_source = articles[0].source
    if first_article_source.url is not None:
        news_source = Source(
            type=SourceType.NEWS,
            name=first_article_source.name,
            url=first_article_source.url,
        )
        if not any(_same_source(source, news_source) for source in updated_sources):
            updated_sources.append(news_source)

    updated_module_results = validated_state.module_results.model_copy(
        update={"sentiment": sentiment_result}
    )
    updated_diagnostics = validated_state.diagnostics.model_copy(
        update={
            "degraded_modules": degraded_modules,
            "warnings": warnings,
        }
    )

    return validated_state.model_copy(
        update={
            "module_results": updated_module_results,
            "diagnostics": updated_diagnostics,
            "sources": updated_sources,
        }
    )


def _run_awaitable(awaitable: Awaitable[AwaitableT]) -> AwaitableT:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, awaitable).result()


def _same_source(left: Source, right: Source) -> bool:
    return (
        left.type == right.type
        and left.name == right.name
        and str(left.url) == str(right.url)
    )

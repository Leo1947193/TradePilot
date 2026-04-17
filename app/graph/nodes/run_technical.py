from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, TypeVar

from app.schemas.api import Source, SourceType
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import (
    AnalysisDirection,
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.interfaces import MarketDataProvider


TECHNICAL_DEGRADED_SUMMARY = "Technical analysis is degraded because provider-backed market data is not available yet."
TECHNICAL_DEGRADED_REASON = "technical module placeholder until provider integration is implemented"
TECHNICAL_DEGRADED_WARNING = "Technical analysis degraded: provider-backed market data is not available yet."
TECHNICAL_USABLE_SUMMARY = "Technical analysis has provider-backed market bars, but the current V1 placeholder keeps the signal neutral until full rules are implemented."

AwaitableT = TypeVar("AwaitableT")


def run_technical(
    state: TradePilotState | dict,
    market_data_provider: MarketDataProvider | None = None,
) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if market_data_provider is not None:
        provider_backed_state = _try_provider_backed_result(validated_state, market_data_provider)
        if provider_backed_state is not None:
            return provider_backed_state

    technical_result = AnalysisModuleResult(
        module=AnalysisModuleName.TECHNICAL,
        status=ModuleExecutionStatus.DEGRADED,
        summary=TECHNICAL_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=TECHNICAL_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.TECHNICAL.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.TECHNICAL.value)

    warnings = list(validated_state.diagnostics.warnings)
    if TECHNICAL_DEGRADED_WARNING not in warnings:
        warnings.append(TECHNICAL_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"technical": technical_result}
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
    market_data_provider: MarketDataProvider,
) -> TradePilotState | None:
    normalized_ticker = validated_state.normalized_ticker
    analysis_window_days = validated_state.context.analysis_window_days
    if normalized_ticker is None or not normalized_ticker.strip():
        return None
    if analysis_window_days is None:
        return None

    try:
        bars = _run_awaitable(
            market_data_provider.get_daily_bars(
                normalized_ticker,
                lookback_days=analysis_window_days[1],
            )
        )
    except Exception:
        return None

    if not bars:
        return None

    technical_result = AnalysisModuleResult(
        module=AnalysisModuleName.TECHNICAL,
        status=ModuleExecutionStatus.USABLE,
        summary=TECHNICAL_USABLE_SUMMARY,
        direction=AnalysisDirection.NEUTRAL,
        data_completeness_pct=100.0,
        low_confidence=False,
        reason=None,
    )

    degraded_modules = [
        module_name
        for module_name in validated_state.diagnostics.degraded_modules
        if module_name != AnalysisModuleName.TECHNICAL.value
    ]
    warnings = [
        warning
        for warning in validated_state.diagnostics.warnings
        if warning != TECHNICAL_DEGRADED_WARNING
    ]

    updated_sources = list(validated_state.sources)
    first_bar_source = bars[0].source
    if first_bar_source.url is not None:
        technical_source = Source(
            type=SourceType.TECHNICAL,
            name=first_bar_source.name,
            url=first_bar_source.url,
        )
        if not any(_same_source(source, technical_source) for source in updated_sources):
            updated_sources.append(technical_source)

    updated_module_results = validated_state.module_results.model_copy(
        update={"technical": technical_result}
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

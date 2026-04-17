from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, TypeVar

from app.analysis.fundamental import analyze_financial_snapshot
from app.schemas.api import Source, SourceType
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import (
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.interfaces import FinancialDataProvider


FUNDAMENTAL_DEGRADED_SUMMARY = (
    "Fundamental analysis is degraded because provider-backed financial data is not available yet."
)
FUNDAMENTAL_DEGRADED_REASON = (
    "fundamental module placeholder until provider integration is implemented"
)
FUNDAMENTAL_DEGRADED_WARNING = (
    "Fundamental analysis degraded: provider-backed financial data is not available yet."
)

AwaitableT = TypeVar("AwaitableT")


def run_fundamental(
    state: TradePilotState | dict,
    financial_data_provider: FinancialDataProvider | None = None,
) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if financial_data_provider is not None:
        provider_backed_state = _try_provider_backed_result(validated_state, financial_data_provider)
        if provider_backed_state is not None:
            return provider_backed_state

    fundamental_result = AnalysisModuleResult(
        module=AnalysisModuleName.FUNDAMENTAL,
        status=ModuleExecutionStatus.DEGRADED,
        summary=FUNDAMENTAL_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=FUNDAMENTAL_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.FUNDAMENTAL.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.FUNDAMENTAL.value)

    warnings = list(validated_state.diagnostics.warnings)
    if FUNDAMENTAL_DEGRADED_WARNING not in warnings:
        warnings.append(FUNDAMENTAL_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"fundamental": fundamental_result}
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
    financial_data_provider: FinancialDataProvider,
) -> TradePilotState | None:
    normalized_ticker = validated_state.normalized_ticker
    if normalized_ticker is None or not normalized_ticker.strip():
        return None

    try:
        snapshot = _run_awaitable(
            financial_data_provider.get_financial_snapshot(normalized_ticker)
        )
    except Exception:
        return None

    if snapshot is None:
        return None

    fundamental_signal = analyze_financial_snapshot(snapshot)

    fundamental_result = AnalysisModuleResult(
        module=AnalysisModuleName.FUNDAMENTAL,
        status=ModuleExecutionStatus.USABLE,
        summary=fundamental_signal.summary,
        direction=fundamental_signal.direction,
        data_completeness_pct=fundamental_signal.data_completeness_pct,
        low_confidence=fundamental_signal.low_confidence,
        reason=None,
    )

    degraded_modules = [
        module_name
        for module_name in validated_state.diagnostics.degraded_modules
        if module_name != AnalysisModuleName.FUNDAMENTAL.value
    ]
    warnings = [
        warning
        for warning in validated_state.diagnostics.warnings
        if warning != FUNDAMENTAL_DEGRADED_WARNING
    ]

    updated_sources = list(validated_state.sources)
    if snapshot.source.url is not None:
        financial_source = Source(
            type=SourceType.FINANCIAL,
            name=snapshot.source.name,
            url=snapshot.source.url,
        )
        if not any(_same_source(source, financial_source) for source in updated_sources):
            updated_sources.append(financial_source)

    updated_module_results = validated_state.module_results.model_copy(
        update={"fundamental": fundamental_result}
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

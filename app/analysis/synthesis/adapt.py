from __future__ import annotations

from app.analysis.synthesis.schemas import (
    NormalizedModuleSignal,
)
from app.rules.decision import (
    CONFIGURED_WEIGHTS,
    DEGRADED_COMPLETENESS_PROXY,
    EXCLUDED_COMPLETENESS_PROXY,
    MODULE_ORDER,
)
from app.schemas.api import FundamentalBias, ModuleName, ModuleStatus
from app.schemas.graph_state import ModuleResults
from app.schemas.modules import AnalysisDirection, AnalysisModuleResult, ModuleExecutionStatus


def adapt_module_signals(module_results: ModuleResults) -> list[NormalizedModuleSignal]:
    result_by_module = {
        ModuleName.TECHNICAL: module_results.technical,
        ModuleName.FUNDAMENTAL: module_results.fundamental,
        ModuleName.SENTIMENT: module_results.sentiment,
        ModuleName.EVENT: module_results.event,
    }

    return [
        adapt_module_signal(module=module, result=result_by_module[module])
        for module in MODULE_ORDER
    ]


def adapt_module_signal(
    module: ModuleName,
    result: AnalysisModuleResult | None,
) -> NormalizedModuleSignal:
    if result is None:
        return NormalizedModuleSignal(
            module=module,
            enabled=False,
            status=ModuleStatus.NOT_ENABLED,
            direction=FundamentalBias.NEUTRAL,
            direction_value=0,
            configured_weight=CONFIGURED_WEIGHTS[module],
            data_completeness_pct=None,
            low_confidence=False,
        )

    direction = _map_direction(result.direction)

    return NormalizedModuleSignal(
        module=module,
        enabled=True,
        status=ModuleStatus(result.status.value),
        direction=direction,
        direction_value=_map_direction_value(direction),
        configured_weight=CONFIGURED_WEIGHTS[module],
        data_completeness_pct=_resolve_data_completeness(result),
        low_confidence=result.low_confidence,
        summary=result.summary or result.reason,
    )


def _map_direction(direction: AnalysisDirection | None) -> FundamentalBias:
    if direction is None:
        return FundamentalBias.NEUTRAL

    return FundamentalBias(direction.value)


def _map_direction_value(direction: FundamentalBias) -> int:
    if direction == FundamentalBias.BULLISH:
        return 1
    if direction in {FundamentalBias.BEARISH, FundamentalBias.DISQUALIFIED}:
        return -1
    return 0


def _resolve_data_completeness(result: AnalysisModuleResult) -> float | None:
    if result.status == ModuleExecutionStatus.NOT_ENABLED:
        return None
    if result.status == ModuleExecutionStatus.EXCLUDED:
        return EXCLUDED_COMPLETENESS_PROXY
    if result.data_completeness_pct is not None:
        return result.data_completeness_pct
    if result.status == ModuleExecutionStatus.DEGRADED:
        return DEGRADED_COMPLETENESS_PROXY
    return 100.0

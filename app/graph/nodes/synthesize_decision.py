from __future__ import annotations

from app.analysis.decision import analyze_decision_signal
from app.schemas.api import (
    AppliedWeights,
    ConfiguredWeights,
    DecisionSynthesis,
    FundamentalBias,
    ModuleContribution,
    ModuleName,
    ModuleStatus,
    TechnicalSetupState,
    WeightSchemeUsed,
)
from app.schemas.graph_state import TradePilotState
from app.schemas.modules import (
    AnalysisDirection,
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)


CONFIGURED_WEIGHTS = {
    ModuleName.TECHNICAL: 0.5,
    ModuleName.FUNDAMENTAL: 0.1,
    ModuleName.SENTIMENT: 0.2,
    ModuleName.EVENT: 0.2,
}
MODULE_ORDER = (
    ModuleName.TECHNICAL,
    ModuleName.FUNDAMENTAL,
    ModuleName.SENTIMENT,
    ModuleName.EVENT,
)
DEGRADED_COMPLETENESS_PROXY = 70.0
EXCLUDED_COMPLETENESS_PROXY = 0.0


def synthesize_decision(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)
    module_results = validated_state.module_results

    result_by_module = {
        ModuleName.TECHNICAL: module_results.technical,
        ModuleName.FUNDAMENTAL: module_results.fundamental,
        ModuleName.SENTIMENT: module_results.sentiment,
        ModuleName.EVENT: module_results.event,
    }

    enabled_modules = [module for module in MODULE_ORDER if result_by_module[module] is not None]
    disabled_modules = [module for module in MODULE_ORDER if result_by_module[module] is None]

    enabled_weight_sum = round(sum(CONFIGURED_WEIGHTS[module] for module in enabled_modules), 4)
    available_modules = [
        module
        for module in MODULE_ORDER
        if _is_available(result_by_module[module])
    ]
    available_weight_sum = round(sum(CONFIGURED_WEIGHTS[module] for module in available_modules), 4)
    available_weight_ratio = round(
        available_weight_sum / enabled_weight_sum if enabled_weight_sum else 0.0,
        4,
    )

    applied_weight_map = _build_applied_weight_map(available_modules, available_weight_sum)
    module_contributions = [
        _build_module_contribution(
            module=module,
            result=result_by_module[module],
            applied_weight=applied_weight_map[module],
        )
        for module in MODULE_ORDER
    ]

    bias_score = round(
        sum(contribution.contribution or 0.0 for contribution in module_contributions),
        2,
    )
    data_completeness_pct = round(
        _calculate_data_completeness_pct(enabled_modules, module_contributions, enabled_weight_sum),
        1,
    )

    usable_modules = [
        module
        for module in MODULE_ORDER
        if result_by_module[module] is not None
        and result_by_module[module].status == ModuleExecutionStatus.USABLE
    ]

    decision_signal = analyze_decision_signal(
        module_contributions,
        available_weight_ratio=available_weight_ratio,
        usable_module_count=len(usable_modules),
    )
    decision_synthesis = DecisionSynthesis(
        overall_bias=decision_signal.overall_bias,
        bias_score=bias_score,
        confidence_score=decision_signal.confidence_score,
        actionability_state=decision_signal.actionability_state,
        conflict_state=decision_signal.conflict_state,
        data_completeness_pct=data_completeness_pct,
        weight_scheme_used=WeightSchemeUsed(
            configured_weights=ConfiguredWeights(
                technical=CONFIGURED_WEIGHTS[ModuleName.TECHNICAL],
                fundamental=CONFIGURED_WEIGHTS[ModuleName.FUNDAMENTAL],
                sentiment=CONFIGURED_WEIGHTS[ModuleName.SENTIMENT],
                event=CONFIGURED_WEIGHTS[ModuleName.EVENT],
            ),
            enabled_modules=enabled_modules,
            disabled_modules=disabled_modules,
            enabled_weight_sum=enabled_weight_sum,
            available_weight_sum=available_weight_sum,
            available_weight_ratio=available_weight_ratio,
            applied_weights=AppliedWeights(
                technical=applied_weight_map[ModuleName.TECHNICAL],
                fundamental=applied_weight_map[ModuleName.FUNDAMENTAL],
                sentiment=applied_weight_map[ModuleName.SENTIMENT],
                event=applied_weight_map[ModuleName.EVENT],
            ),
            renormalized=bool(
                enabled_modules and any(module not in available_modules for module in enabled_modules)
            ),
        ),
        blocking_flags=decision_signal.blocking_flags,
        module_contributions=module_contributions,
        risks=_build_risks(
            usable_modules=usable_modules,
            available_weight_ratio=available_weight_ratio,
            module_contributions=module_contributions,
        ),
    )

    return validated_state.model_copy(update={"decision_synthesis": decision_synthesis})


def _is_available(result: AnalysisModuleResult | None) -> bool:
    if result is None:
        return False

    return result.status in {
        ModuleExecutionStatus.USABLE,
        ModuleExecutionStatus.DEGRADED,
    }


def _build_applied_weight_map(
    available_modules: list[ModuleName],
    available_weight_sum: float,
) -> dict[ModuleName, float | None]:
    applied_weight_map: dict[ModuleName, float | None] = {module: None for module in MODULE_ORDER}
    if not available_modules or not available_weight_sum:
        return applied_weight_map

    for module in available_modules:
        applied_weight_map[module] = round(CONFIGURED_WEIGHTS[module] / available_weight_sum, 4)

    return applied_weight_map


def _build_module_contribution(
    module: ModuleName,
    result: AnalysisModuleResult | None,
    applied_weight: float | None,
) -> ModuleContribution:
    if result is None:
        return ModuleContribution(
            module=module,
            enabled=False,
            status=ModuleStatus.NOT_ENABLED,
            direction=FundamentalBias.NEUTRAL,
            direction_value=0,
            configured_weight=CONFIGURED_WEIGHTS[module],
            applied_weight=None,
            contribution=None,
            data_completeness_pct=None,
            low_confidence=False,
        )

    direction = _map_direction(result.direction)
    direction_value = _map_direction_value(direction)
    completeness = _resolve_data_completeness(result)
    contribution = None if applied_weight is None else round(direction_value * applied_weight, 4)

    return ModuleContribution(
        module=module,
        enabled=True,
        status=ModuleStatus(result.status.value),
        direction=direction,
        direction_value=direction_value,
        configured_weight=CONFIGURED_WEIGHTS[module],
        applied_weight=applied_weight,
        contribution=contribution,
        data_completeness_pct=completeness,
        low_confidence=result.low_confidence,
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


def _calculate_data_completeness_pct(
    enabled_modules: list[ModuleName],
    module_contributions: list[ModuleContribution],
    enabled_weight_sum: float,
) -> float:
    if not enabled_modules or not enabled_weight_sum:
        return 0.0

    completeness_by_module = {contribution.module: contribution for contribution in module_contributions}
    weighted_sum = 0.0
    for module in enabled_modules:
        contribution = completeness_by_module[module]
        completeness = contribution.data_completeness_pct or 0.0
        weighted_sum += (completeness / 100) * CONFIGURED_WEIGHTS[module]

    return 100 * (weighted_sum / enabled_weight_sum)


def _build_risks(
    usable_modules: list[ModuleName],
    available_weight_ratio: float,
    module_contributions: list[ModuleContribution],
) -> list[str]:
    risks: list[str] = []

    if not usable_modules:
        risks.append("当前仅有降级模块结果，综合结论不具备可执行性")

    if available_weight_ratio < 0.70 or not usable_modules:
        risks.append("关键模块证据不足，当前综合结论稳定性受限")

    degraded_modules = [
        contribution.module.value
        for contribution in module_contributions
        if contribution.status == ModuleStatus.DEGRADED
    ]
    if degraded_modules:
        risks.append(f"降级模块较多：{', '.join(degraded_modules)}")

    return risks[:6]

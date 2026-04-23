from __future__ import annotations

from app.analysis.decision import analyze_decision_signal
from app.analysis.synthesis.schemas import (
    NormalizedModuleSignal,
    ScoredDecision,
)
from app.rules.decision import CONFIGURED_WEIGHTS, MODULE_ORDER
from app.schemas.api import ModuleContribution, ModuleName, ModuleStatus


def score_decision(normalized_signals: list[NormalizedModuleSignal]) -> ScoredDecision:
    signal_by_module = {signal.module: signal for signal in normalized_signals}

    enabled_modules = [module for module in MODULE_ORDER if signal_by_module[module].enabled]
    disabled_modules = [module for module in MODULE_ORDER if not signal_by_module[module].enabled]
    enabled_weight_sum = round(sum(CONFIGURED_WEIGHTS[module] for module in enabled_modules), 4)

    available_modules = [
        module for module in MODULE_ORDER if _is_available(signal_by_module[module])
    ]
    available_weight_sum = round(sum(CONFIGURED_WEIGHTS[module] for module in available_modules), 4)
    available_weight_ratio = round(
        available_weight_sum / enabled_weight_sum if enabled_weight_sum else 0.0,
        4,
    )

    applied_weight_map = _build_applied_weight_map(available_modules, available_weight_sum)
    module_contributions = [
        _build_module_contribution(signal_by_module[module], applied_weight_map[module])
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
        if signal_by_module[module].enabled and signal_by_module[module].status == ModuleStatus.USABLE
    ]

    decision_signal = analyze_decision_signal(
        normalized_signals,
        module_contributions,
        available_weight_ratio=available_weight_ratio,
        usable_module_count=len(usable_modules),
    )

    return ScoredDecision(
        normalized_signals=normalized_signals,
        enabled_modules=enabled_modules,
        disabled_modules=disabled_modules,
        available_modules=available_modules,
        usable_modules=usable_modules,
        enabled_weight_sum=enabled_weight_sum,
        available_weight_sum=available_weight_sum,
        available_weight_ratio=available_weight_ratio,
        applied_weight_map=applied_weight_map,
        module_contributions=module_contributions,
        bias_score=bias_score,
        data_completeness_pct=data_completeness_pct,
        decision_signal=decision_signal,
    )


def _is_available(signal: NormalizedModuleSignal) -> bool:
    return signal.status in {
        ModuleStatus.USABLE,
        ModuleStatus.DEGRADED,
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
    signal: NormalizedModuleSignal,
    applied_weight: float | None,
) -> ModuleContribution:
    contribution = None if applied_weight is None else round(signal.direction_value * applied_weight, 4)

    return ModuleContribution(
        module=signal.module,
        enabled=signal.enabled,
        status=signal.status,
        direction=signal.direction,
        direction_value=signal.direction_value,
        configured_weight=signal.configured_weight,
        applied_weight=applied_weight,
        contribution=contribution,
        data_completeness_pct=signal.data_completeness_pct,
        low_confidence=signal.low_confidence,
    )


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

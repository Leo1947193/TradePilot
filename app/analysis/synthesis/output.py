from __future__ import annotations

from app.analysis.synthesis.schemas import ScoredDecision
from app.rules.decision import CONFIGURED_WEIGHTS, RISK_EVIDENCE_WEIGHT_RATIO_FLOOR
from app.rules.messages import (
    SYNTHESIS_INSUFFICIENT_EVIDENCE_RISK,
    SYNTHESIS_ONLY_DEGRADED_RESULTS_RISK,
)
from app.schemas.api import (
    AppliedWeights,
    ConfiguredWeights,
    DecisionSynthesis,
    ModuleContribution,
    ModuleName,
    ModuleStatus,
    WeightSchemeUsed,
)


def build_decision_output(scored_decision: ScoredDecision) -> DecisionSynthesis:
    return DecisionSynthesis(
        overall_bias=scored_decision.decision_signal.overall_bias,
        bias_score=scored_decision.bias_score,
        confidence_score=scored_decision.decision_signal.confidence_score,
        actionability_state=scored_decision.decision_signal.actionability_state,
        conflict_state=scored_decision.decision_signal.conflict_state,
        data_completeness_pct=scored_decision.data_completeness_pct,
        weight_scheme_used=WeightSchemeUsed(
            configured_weights=ConfiguredWeights(
                technical=CONFIGURED_WEIGHTS[ModuleName.TECHNICAL],
                fundamental=CONFIGURED_WEIGHTS[ModuleName.FUNDAMENTAL],
                sentiment=CONFIGURED_WEIGHTS[ModuleName.SENTIMENT],
                event=CONFIGURED_WEIGHTS[ModuleName.EVENT],
            ),
            enabled_modules=scored_decision.enabled_modules,
            disabled_modules=scored_decision.disabled_modules,
            enabled_weight_sum=scored_decision.enabled_weight_sum,
            available_weight_sum=scored_decision.available_weight_sum,
            available_weight_ratio=scored_decision.available_weight_ratio,
            applied_weights=AppliedWeights(
                technical=scored_decision.applied_weight_map[ModuleName.TECHNICAL],
                fundamental=scored_decision.applied_weight_map[ModuleName.FUNDAMENTAL],
                sentiment=scored_decision.applied_weight_map[ModuleName.SENTIMENT],
                event=scored_decision.applied_weight_map[ModuleName.EVENT],
            ),
            renormalized=bool(
                scored_decision.enabled_modules
                and any(
                    module not in scored_decision.available_modules
                    for module in scored_decision.enabled_modules
                )
            ),
        ),
        blocking_flags=scored_decision.decision_signal.blocking_flags,
        module_contributions=scored_decision.module_contributions,
        risks=_build_risks(
            usable_modules=scored_decision.usable_modules,
            available_weight_ratio=scored_decision.available_weight_ratio,
            module_contributions=scored_decision.module_contributions,
        ),
    )


def _build_risks(
    usable_modules: list[ModuleName],
    available_weight_ratio: float,
    module_contributions: list[ModuleContribution],
) -> list[str]:
    risks: list[str] = []

    if not usable_modules:
        risks.append(SYNTHESIS_ONLY_DEGRADED_RESULTS_RISK)

    if available_weight_ratio < RISK_EVIDENCE_WEIGHT_RATIO_FLOOR or not usable_modules:
        risks.append(SYNTHESIS_INSUFFICIENT_EVIDENCE_RISK)

    degraded_modules = [
        contribution.module.value
        for contribution in module_contributions
        if contribution.status == ModuleStatus.DEGRADED
    ]
    if degraded_modules:
        risks.append(f"降级模块较多：{', '.join(degraded_modules)}")

    return risks[:6]

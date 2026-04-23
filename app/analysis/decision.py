from __future__ import annotations

from dataclasses import dataclass

from app.rules.decision import DECISION_THRESHOLDS
from app.rules.messages import EVENT_RISK_BLOCKING_FLAG
from app.schemas.api import ConflictState, Direction, ModuleContribution, ModuleName, TechnicalSetupState
from app.schemas.api import FundamentalBias as PublicDirection


@dataclass(frozen=True)
class DecisionSignal:
    overall_bias: Direction
    confidence_score: float
    actionability_state: TechnicalSetupState
    conflict_state: ConflictState
    blocking_flags: list[str]


def analyze_decision_signal(
    normalized_signals,
    module_contributions: list[ModuleContribution],
    *,
    available_weight_ratio: float,
    usable_module_count: int,
) -> DecisionSignal:
    bias_score = sum(contribution.contribution or 0.0 for contribution in module_contributions)
    overall_bias = _resolve_overall_bias(bias_score)
    conflict_state = _determine_conflict_state(module_contributions)
    blocking_flags = _build_blocking_flags(normalized_signals, module_contributions)
    confidence_score = _calculate_confidence(
        module_contributions,
        overall_bias=overall_bias,
        available_weight_ratio=available_weight_ratio,
        usable_module_count=usable_module_count,
        conflict_state=conflict_state,
    )
    actionability_state = _resolve_actionability(
        overall_bias=overall_bias,
        confidence_score=confidence_score,
        conflict_state=conflict_state,
        blocking_flags=blocking_flags,
        usable_module_count=usable_module_count,
    )

    return DecisionSignal(
        overall_bias=overall_bias,
        confidence_score=confidence_score,
        actionability_state=actionability_state,
        conflict_state=conflict_state,
        blocking_flags=blocking_flags,
    )


def _resolve_overall_bias(bias_score: float) -> Direction:
    if bias_score >= DECISION_THRESHOLDS.bullish_bias_score:
        return Direction.BULLISH
    if bias_score <= DECISION_THRESHOLDS.bearish_bias_score:
        return Direction.BEARISH
    return Direction.NEUTRAL


def _calculate_confidence(
    module_contributions: list[ModuleContribution],
    *,
    overall_bias: Direction,
    available_weight_ratio: float,
    usable_module_count: int,
    conflict_state: ConflictState,
) -> float:
    if usable_module_count == 0:
        return 0.0

    supporting_weight = sum(
        contribution.applied_weight or 0.0
        for contribution in module_contributions
        if _supports_bias(contribution.direction, overall_bias)
    )
    low_confidence_penalty = DECISION_THRESHOLDS.low_confidence_penalty if any(
        contribution.low_confidence and _supports_bias(contribution.direction, overall_bias)
        for contribution in module_contributions
    ) else 0.0
    conflict_penalty = (
        DECISION_THRESHOLDS.conflicted_conflict_penalty
        if conflict_state == ConflictState.CONFLICTED
        else DECISION_THRESHOLDS.mixed_conflict_penalty
        if conflict_state == ConflictState.MIXED
        else 0.0
    )

    raw_score = (
        (available_weight_ratio * DECISION_THRESHOLDS.available_weight_ratio_weight)
        + (supporting_weight * DECISION_THRESHOLDS.supporting_weight_weight)
        - low_confidence_penalty
        - conflict_penalty
    )
    return round(max(0.0, min(1.0, raw_score)), 2)


def _resolve_actionability(
    *,
    overall_bias: Direction,
    confidence_score: float,
    conflict_state: ConflictState,
    blocking_flags: list[str],
    usable_module_count: int,
) -> TechnicalSetupState:
    if usable_module_count == 0 or blocking_flags:
        return TechnicalSetupState.AVOID
    if (
        overall_bias == Direction.NEUTRAL
        or confidence_score < DECISION_THRESHOLDS.actionable_confidence_floor
        or conflict_state == ConflictState.CONFLICTED
    ):
        return TechnicalSetupState.WATCH
    return TechnicalSetupState.ACTIONABLE


def _build_blocking_flags(normalized_signals, module_contributions: list[ModuleContribution]) -> list[str]:
    flags: list[str] = []

    event_signal = next(
        (signal for signal in normalized_signals if signal.module == ModuleName.EVENT),
        None,
    )
    if event_signal is not None:
        for flag in event_signal.blocking_flags:
            if flag not in flags:
                flags.append(flag)
    if flags:
        return flags

    event_contribution = next(
        (contribution for contribution in module_contributions if contribution.module == ModuleName.EVENT),
        None,
    )
    if event_contribution is not None and event_contribution.direction in {
        PublicDirection.BEARISH,
        PublicDirection.DISQUALIFIED,
    }:
        flags.append(EVENT_RISK_BLOCKING_FLAG)

    return flags


def _determine_conflict_state(
    module_contributions: list[ModuleContribution],
) -> ConflictState:
    bullish_weight = sum(
        contribution.applied_weight or 0.0
        for contribution in module_contributions
        if contribution.direction == PublicDirection.BULLISH
    )
    bearish_weight = sum(
        contribution.applied_weight or 0.0
        for contribution in module_contributions
        if contribution.direction in {PublicDirection.BEARISH, PublicDirection.DISQUALIFIED}
    )

    if bullish_weight == 0 or bearish_weight == 0:
        return ConflictState.ALIGNED
    if abs(bullish_weight - bearish_weight) >= DECISION_THRESHOLDS.mixed_conflict_weight_gap:
        return ConflictState.MIXED
    return ConflictState.CONFLICTED


def _supports_bias(direction: PublicDirection, overall_bias: Direction) -> bool:
    if overall_bias == Direction.BULLISH:
        return direction == PublicDirection.BULLISH
    if overall_bias == Direction.BEARISH:
        return direction in {PublicDirection.BEARISH, PublicDirection.DISQUALIFIED}
    return direction == PublicDirection.NEUTRAL

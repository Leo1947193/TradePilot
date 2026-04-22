from __future__ import annotations

from dataclasses import dataclass

from app.schemas.api import ModuleName


@dataclass(frozen=True)
class DecisionThresholds:
    bullish_bias_score: float = 0.15
    bearish_bias_score: float = -0.15
    available_weight_ratio_weight: float = 0.55
    supporting_weight_weight: float = 0.45
    low_confidence_penalty: float = 0.1
    mixed_conflict_penalty: float = 0.1
    conflicted_conflict_penalty: float = 0.2
    actionable_confidence_floor: float = 0.45
    mixed_conflict_weight_gap: float = 0.30


DECISION_THRESHOLDS = DecisionThresholds()

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
RISK_EVIDENCE_WEIGHT_RATIO_FLOOR = 0.70

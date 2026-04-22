from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.analysis.decision import DecisionSignal
from app.rules.decision import CONFIGURED_WEIGHTS, MODULE_ORDER
from app.schemas.api import FundamentalBias, ModuleContribution, ModuleName, ModuleStatus


DirectionValue = Literal[-1, 0, 1]


@dataclass(frozen=True)
class NormalizedModuleSignal:
    module: ModuleName
    enabled: bool
    status: ModuleStatus
    direction: FundamentalBias
    direction_value: DirectionValue
    configured_weight: float
    data_completeness_pct: float | None
    low_confidence: bool
    blocking_flags: list[str] = field(default_factory=list)
    diagnostic_flags: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    summary: str | None = None


@dataclass(frozen=True)
class ScoredDecision:
    normalized_signals: list[NormalizedModuleSignal]
    enabled_modules: list[ModuleName]
    disabled_modules: list[ModuleName]
    available_modules: list[ModuleName]
    usable_modules: list[ModuleName]
    enabled_weight_sum: float
    available_weight_sum: float
    available_weight_ratio: float
    applied_weight_map: dict[ModuleName, float | None]
    module_contributions: list[ModuleContribution]
    bias_score: float
    data_completeness_pct: float
    decision_signal: DecisionSignal

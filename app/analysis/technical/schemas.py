from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from app.schemas.api import TechnicalSetupState, VolumePattern
from app.schemas.modules import AnalysisDirection, ModuleSchema


class TechnicalSignal(ModuleSchema):
    model_config = ConfigDict(extra="forbid")

    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


class TechnicalAggregateResult(ModuleSchema):
    model_config = ConfigDict(extra="forbid")

    technical_signal: AnalysisDirection
    trend: AnalysisDirection
    setup_state: TechnicalSetupState
    summary: str
    data_completeness_pct: float
    low_confidence: bool
    risk_flags: list[str]
    key_support: list[float]
    key_resistance: list[float]
    volume_pattern: VolumePattern
    entry_trigger: str | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    risk_reward_ratio: float | None = None
    subsignals: dict[str, TechnicalSignal]


class TechnicalSubmoduleBundle(ModuleSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    multi_timeframe: Any
    momentum: Any
    volume_price: Any
    risk_metrics: Any
    patterns: Any

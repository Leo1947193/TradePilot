from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from app.schemas.modules import AnalysisDirection, ModuleSchema


class FundamentalSignal(ModuleSchema):
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool
    positive_signals: int
    negative_signals: int
    present_fields: int
    total_fields: int
    key_metrics: list[str]


class FundamentalAggregateResult(ModuleSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    fundamental_bias: AnalysisDirection
    composite_score: float
    key_risks: list[str]
    data_completeness_pct: float
    low_confidence: bool
    low_confidence_modules: list[str]
    weight_scheme_used: str
    subresults: dict[str, Any]
    summary: str


class FundamentalSubmoduleBundle(ModuleSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    financial_snapshot: FundamentalSignal
    financial_health: Any
    earnings_momentum: Any
    valuation_anchor: Any

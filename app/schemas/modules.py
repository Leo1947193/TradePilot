from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModuleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisModuleName(StrEnum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    EVENT = "event"


class ModuleExecutionStatus(StrEnum):
    USABLE = "usable"
    DEGRADED = "degraded"
    EXCLUDED = "excluded"
    NOT_ENABLED = "not_enabled"


class AnalysisDirection(StrEnum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    DISQUALIFIED = "disqualified"


class AnalysisModuleResult(ModuleSchema):
    module: AnalysisModuleName
    status: ModuleExecutionStatus
    summary: str | None = None
    direction: AnalysisDirection | None = None
    data_completeness_pct: float | None = Field(default=None, ge=0, le=100)
    low_confidence: bool = False
    reason: str | None = None

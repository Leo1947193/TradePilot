from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints


Ticker = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
BiasScore = Annotated[float, Field(ge=-1, le=1)]
ConfidenceScore = Annotated[float, Field(ge=0, le=1)]
DataCompletenessPct = Annotated[float, Field(ge=0, le=100)]
ModuleContributions = Annotated[list["ModuleContribution"], Field(min_length=4, max_length=4)]


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Direction(StrEnum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class TechnicalSetupState(StrEnum):
    ACTIONABLE = "actionable"
    WATCH = "watch"
    AVOID = "avoid"


class VolumePattern(StrEnum):
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    NEUTRAL = "neutral"
    PULLBACK_HEALTHY = "pullback_healthy"
    BOUNCE_WEAK = "bounce_weak"


class FundamentalBias(StrEnum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    DISQUALIFIED = "disqualified"


class NewsTone(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ConflictState(StrEnum):
    ALIGNED = "aligned"
    MIXED = "mixed"
    CONFLICTED = "conflicted"


class ModuleName(StrEnum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    EVENT = "event"


class ModuleStatus(StrEnum):
    USABLE = "usable"
    DEGRADED = "degraded"
    EXCLUDED = "excluded"
    NOT_ENABLED = "not_enabled"


class SourceType(StrEnum):
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    NEWS = "news"
    MACRO = "macro"
    EVENT = "event"


class EventRiskFlag(StrEnum):
    BINARY_EVENT_IMMINENT = "binary_event_imminent"
    EARNINGS_WITHIN_3D = "earnings_within_3d"
    REGULATORY_DECISION_IMMINENT = "regulatory_decision_imminent"
    MACRO_EVENT_HIGH_SENSITIVITY = "macro_event_high_sensitivity"


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason: str


class ErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorObject


class TechnicalAnalysis(ApiSchema):
    technical_signal: Direction
    trend: Direction
    key_support: list[float]
    key_resistance: list[float]
    volume_pattern: VolumePattern
    momentum: str
    entry_trigger: str | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    risk_reward_ratio: float | None = None
    risk_flags: list[str]
    setup_state: TechnicalSetupState
    technical_summary: str


class FundamentalAnalysis(ApiSchema):
    fundamental_bias: FundamentalBias
    composite_score: float
    growth: str
    valuation_view: str
    business_quality: str
    key_risks: list[str]
    data_completeness_pct: DataCompletenessPct
    fundamental_summary: str


class SentimentExpectations(ApiSchema):
    sentiment_bias: Direction
    news_tone: NewsTone
    market_expectation: str
    key_risks: list[str]
    data_completeness_pct: DataCompletenessPct
    sentiment_summary: str | None = None


class EventDrivenAnalysis(ApiSchema):
    event_bias: Direction
    upcoming_catalysts: list[str]
    risk_events: list[str]
    event_risk_flags: list[EventRiskFlag]
    data_completeness_pct: DataCompletenessPct
    event_summary: str | None = None


class ConfiguredWeights(ApiSchema):
    technical: float
    fundamental: float
    sentiment: float
    event: float


class AppliedWeights(ApiSchema):
    technical: float | None
    fundamental: float | None
    sentiment: float | None
    event: float | None


class ModuleContribution(ApiSchema):
    module: ModuleName
    enabled: bool
    status: ModuleStatus
    direction: FundamentalBias
    direction_value: Literal[-1, 0, 1]
    configured_weight: float
    applied_weight: float | None
    contribution: float | None
    data_completeness_pct: DataCompletenessPct | None
    low_confidence: bool


class WeightSchemeUsed(ApiSchema):
    configured_weights: ConfiguredWeights
    enabled_modules: list[ModuleName]
    disabled_modules: list[ModuleName]
    enabled_weight_sum: float
    available_weight_sum: float
    available_weight_ratio: float
    applied_weights: AppliedWeights
    renormalized: bool


class DecisionSynthesis(ApiSchema):
    overall_bias: Direction
    bias_score: BiasScore
    confidence_score: ConfidenceScore
    actionability_state: TechnicalSetupState
    conflict_state: ConflictState
    data_completeness_pct: DataCompletenessPct
    weight_scheme_used: WeightSchemeUsed
    blocking_flags: list[str]
    module_contributions: ModuleContributions
    risks: list[str]


class TradeScenario(ApiSchema):
    entry_idea: str
    take_profit: str
    stop_loss: str


class TradePlan(ApiSchema):
    overall_bias: Direction
    bullish_scenario: TradeScenario
    bearish_scenario: TradeScenario
    do_not_trade_conditions: list[str]


class Source(ApiSchema):
    type: SourceType
    name: str
    url: AnyUrl


class AnalysisResponse(ApiSchema):
    ticker: str
    analysis_time: datetime
    technical_analysis: TechnicalAnalysis
    fundamental_analysis: FundamentalAnalysis
    sentiment_expectations: SentimentExpectations
    event_driven_analysis: EventDrivenAnalysis
    decision_synthesis: DecisionSynthesis
    trade_plan: TradePlan
    sources: list[Source]

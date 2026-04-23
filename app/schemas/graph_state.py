from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.api import AnalyzeRequest, AnalysisResponse, DecisionSynthesis, Source, TradePlan
from app.schemas.modules import AnalysisModuleResult


JsonObject = dict[str, Any]


class GraphStateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GraphContext(GraphStateSchema):
    analysis_time: datetime | None = None
    market: str | None = None
    benchmark: str | None = None
    analysis_window_days: tuple[int, int] | None = None


class ProviderPayloads(GraphStateSchema):
    market: JsonObject | None = None
    financial: JsonObject | None = None
    news: JsonObject | None = None
    company_events: JsonObject | None = None
    macro_calendar: JsonObject | None = None


class ModuleResults(GraphStateSchema):
    technical: AnalysisModuleResult | None = None
    fundamental: AnalysisModuleResult | None = None
    sentiment: AnalysisModuleResult | None = None
    event: AnalysisModuleResult | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_module_names(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        for module_name in ("technical", "fundamental", "sentiment", "event"):
            result = payload.get(module_name)
            if isinstance(result, dict) and "module" not in result:
                payload[module_name] = {"module": module_name, **result}

        return payload


class ModuleReports(GraphStateSchema):
    technical: dict[str, Any] | None = None
    fundamental: dict[str, Any] | None = None
    sentiment: dict[str, Any] | None = None
    event: dict[str, Any] | None = None


class PersistenceStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PersistenceState(GraphStateSchema):
    status: PersistenceStatus = PersistenceStatus.PENDING
    record_id: str | None = None
    persisted_at: datetime | None = None
    error: str | None = None


class DiagnosticsState(GraphStateSchema):
    degraded_modules: list[str] = Field(default_factory=list)
    excluded_modules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TradePilotState(GraphStateSchema):
    request: AnalyzeRequest
    normalized_ticker: str | None = None
    request_id: str
    context: GraphContext = Field(default_factory=GraphContext)
    provider_payloads: ProviderPayloads = Field(default_factory=ProviderPayloads)
    module_results: ModuleResults = Field(default_factory=ModuleResults)
    module_reports: ModuleReports = Field(default_factory=ModuleReports)
    decision_synthesis: DecisionSynthesis | None = None
    trade_plan: TradePlan | None = None
    response: AnalysisResponse | None = None
    sources: list[Source] = Field(default_factory=list)
    persistence: PersistenceState = Field(default_factory=PersistenceState)
    diagnostics: DiagnosticsState = Field(default_factory=DiagnosticsState)

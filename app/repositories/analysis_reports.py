from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.api import AnalyzeRequest, AnalysisResponse, DecisionSynthesis, TradePlan
from app.schemas.graph_state import DiagnosticsState, GraphContext, ModuleResults
from app.schemas.api import Source


@dataclass(frozen=True)
class PersistedAnalysisRecord:
    record_id: str
    persisted_at: datetime


@dataclass(frozen=True)
class AnalysisReportPayload:
    request_id: str
    raw_ticker: str
    normalized_ticker: str
    analysis_time: datetime
    request: AnalyzeRequest
    context: GraphContext
    module_results: ModuleResults
    decision_synthesis: DecisionSynthesis
    trade_plan: TradePlan
    response: AnalysisResponse
    sources: list[Source]
    diagnostics: DiagnosticsState


class AnalysisReportRepository(Protocol):
    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        """Persist an analysis snapshot and return the storage metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.api import Source
from app.schemas.api import AnalyzeRequest, AnalysisResponse, DecisionSynthesis, TradePlan
from app.schemas.graph_state import DiagnosticsState, GraphContext, ModuleResults


@dataclass(frozen=True)
class PersistedAnalysisRecord:
    record_id: str
    persisted_at: datetime


@dataclass(frozen=True)
class PersistedAnalysisReport:
    report_id: str
    request_id: str
    normalized_ticker: str
    raw_ticker: str
    analysis_time: datetime
    overall_bias: str
    actionability_state: str
    response: AnalysisResponse
    decision_synthesis: DecisionSynthesis
    trade_plan: TradePlan
    created_at: datetime
    updated_at: datetime


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

    def get_analysis_report(self, report_id: str) -> PersistedAnalysisReport | None:
        """Load a single persisted analysis report by its primary identifier."""

    def list_reports_by_ticker(
        self,
        ticker: str,
        limit: int = 20,
    ) -> list[PersistedAnalysisReport]:
        """List persisted reports for a ticker ordered by newest analysis first."""

    def get_latest_report_by_ticker(self, ticker: str) -> PersistedAnalysisReport | None:
        """Load the most recent persisted report for a ticker."""

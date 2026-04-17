from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.graph.builder import build_analysis_graph
from app.repositories.analysis_reports import AnalysisReportPayload, PersistedAnalysisRecord
from app.schemas.graph_state import PersistenceStatus, TradePilotState


@dataclass
class FakeAnalysisReportRepository:
    captured_payload: AnalysisReportPayload | None = None

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        self.captured_payload = payload
        return PersistedAnalysisRecord(
            record_id="report_graph_123",
            persisted_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        )


def test_build_analysis_graph_runs_end_to_end() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(repository)

    result = graph.invoke({"request": {"ticker": " aapl "}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.normalized_ticker == "AAPL"
    assert final_state.decision_synthesis is not None
    assert final_state.trade_plan is not None
    assert final_state.response is not None
    assert final_state.persistence.status == PersistenceStatus.SUCCEEDED
    assert final_state.persistence.record_id == "report_graph_123"
    assert final_state.module_results.technical is not None
    assert final_state.module_results.fundamental is not None
    assert final_state.module_results.sentiment is not None
    assert final_state.module_results.event is not None
    assert repository.captured_payload is not None
    assert repository.captured_payload.response == final_state.response


def test_build_analysis_graph_topology_matches_v1_order() -> None:
    graph = build_analysis_graph(FakeAnalysisReportRepository())
    topology = graph.get_graph()
    edges = {(edge.source, edge.target) for edge in topology.edges}

    assert ("__start__", "validate_request") in edges
    assert ("validate_request", "prepare_context") in edges
    assert ("prepare_context", "run_technical") in edges
    assert ("prepare_context", "run_fundamental") in edges
    assert ("prepare_context", "run_sentiment") in edges
    assert ("prepare_context", "run_event") in edges
    assert ("run_technical", "synthesize_decision") in edges
    assert ("run_fundamental", "synthesize_decision") in edges
    assert ("run_sentiment", "synthesize_decision") in edges
    assert ("run_event", "synthesize_decision") in edges
    assert ("synthesize_decision", "generate_trade_plan") in edges
    assert ("generate_trade_plan", "assemble_response") in edges
    assert ("assemble_response", "persist_analysis") in edges
    assert ("persist_analysis", "__end__") in edges

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.graph.nodes.assemble_response import assemble_response
from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.graph.nodes.persist_analysis import persist_analysis
from app.graph.nodes.prepare_context import prepare_context
from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.graph.nodes.validate_request import validate_request
from app.repositories.analysis_reports import (
    AnalysisReportPayload,
    PersistedAnalysisRecord,
)
from app.schemas.graph_state import PersistenceStatus


def build_persistable_state():
    state = validate_request({"request": {"ticker": " aapl "}, "request_id": "req_123"})
    state = prepare_context(state)
    state = run_technical(state)
    state = run_fundamental(state)
    state = run_sentiment(state)
    state = run_event(state)
    state = synthesize_decision(state)
    state = generate_trade_plan(state)
    state = assemble_response(state)
    return state


@dataclass
class FakeAnalysisReportRepository:
    result: PersistedAnalysisRecord | None = None
    error: Exception | None = None
    captured_payload: AnalysisReportPayload | None = None

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        self.captured_payload = payload
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_persist_analysis_success_updates_persistence_fields() -> None:
    repository = FakeAnalysisReportRepository(
        result=PersistedAnalysisRecord(
            record_id="report_123",
            persisted_at=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        )
    )

    state = persist_analysis(build_persistable_state(), repository)

    assert state.persistence.status == PersistenceStatus.SUCCEEDED
    assert state.persistence.record_id == "report_123"
    assert state.persistence.persisted_at == datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    assert state.persistence.error is None


def test_persist_analysis_missing_response_fails_fast() -> None:
    state = build_persistable_state().model_copy(update={"response": None})
    repository = FakeAnalysisReportRepository(
        result=PersistedAnalysisRecord(
            record_id="unused",
            persisted_at=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(ValueError, match="response is required to persist analysis"):
        persist_analysis(state, repository)


def test_persist_analysis_repository_failure_marks_failed_and_raises() -> None:
    state = build_persistable_state()
    repository = FakeAnalysisReportRepository(error=RuntimeError("database unavailable"))

    with pytest.raises(RuntimeError, match="analysis report persistence failed"):
        persist_analysis(state, repository)

    assert state.persistence.status == PersistenceStatus.FAILED
    assert state.persistence.record_id is None
    assert state.persistence.persisted_at is None
    assert state.persistence.error == "database unavailable"


def test_persist_analysis_passes_required_payload_to_repository() -> None:
    repository = FakeAnalysisReportRepository(
        result=PersistedAnalysisRecord(
            record_id="report_456",
            persisted_at=datetime(2026, 4, 17, 11, 0, tzinfo=timezone.utc),
        )
    )
    state = build_persistable_state()

    persist_analysis(state, repository)

    assert repository.captured_payload is not None
    assert repository.captured_payload.request == state.request
    assert repository.captured_payload.raw_ticker == state.request.ticker
    assert repository.captured_payload.normalized_ticker == state.normalized_ticker
    assert repository.captured_payload.analysis_time == state.context.analysis_time
    assert repository.captured_payload.context == state.context
    assert repository.captured_payload.module_results == state.module_results
    assert repository.captured_payload.module_reports == state.module_reports
    assert repository.captured_payload.decision_synthesis == state.decision_synthesis
    assert repository.captured_payload.trade_plan == state.trade_plan
    assert repository.captured_payload.response == state.response
    assert repository.captured_payload.sources == state.sources
    assert repository.captured_payload.diagnostics == state.diagnostics

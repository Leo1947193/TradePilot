from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from app.graph.nodes.assemble_response import assemble_response
from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.graph.nodes.prepare_context import prepare_context
from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.graph.nodes.validate_request import validate_request
from app.repositories.postgresql_analysis_reports import (
    INSERT_ANALYSIS_MODULE_REPORT_SQL,
    INSERT_ANALYSIS_REPORT_SQL,
    INSERT_ANALYSIS_SOURCE_SQL,
    PostgreSQLAnalysisReportRepository,
)
from app.repositories.analysis_reports import AnalysisReportPayload


def build_payload() -> AnalysisReportPayload:
    state = validate_request({"request": {"ticker": " aapl "}, "request_id": "req_repo_123"})
    state = prepare_context(state)
    state = run_technical(state)
    state = run_fundamental(state)
    state = run_sentiment(state)
    state = run_event(state)
    state = synthesize_decision(state)
    state = generate_trade_plan(state)
    state = state.model_copy(
        update={
            "sources": [
                {
                    "type": "technical",
                    "name": "provider-a",
                    "url": "https://example.com/a",
                },
                {
                    "type": "news",
                    "name": "provider-b",
                    "url": "https://example.com/b",
                },
            ]
        }
    )
    state = assemble_response(state)
    return AnalysisReportPayload(
        request_id=state.request_id,
        raw_ticker=state.request.ticker,
        normalized_ticker=state.normalized_ticker or "",
        analysis_time=state.context.analysis_time,
        request=state.request,
        context=state.context,
        module_results=state.module_results,
        decision_synthesis=state.decision_synthesis,
        trade_plan=state.trade_plan,
        response=state.response,
        sources=state.sources,
        diagnostics=state.diagnostics,
    )


class FakeCursor:
    def __init__(self, executed: list[tuple[str, dict[str, object]]]) -> None:
        self.executed = executed

    def execute(self, sql: str, params: dict[str, object]) -> None:
        self.executed.append((" ".join(sql.split()), params))

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeTransaction:
    def __init__(self, markers: list[str]) -> None:
        self.markers = markers

    def __enter__(self) -> None:
        self.markers.append("begin")
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        self.markers.append("end")
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []
        self.transaction_markers: list[str] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.executed)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self.transaction_markers)

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


@dataclass
class FakePool:
    connection_obj: FakeConnection

    @contextmanager
    def connection(self):
        yield self.connection_obj


def test_save_analysis_report_inserts_rows_in_required_order() -> None:
    connection = FakeConnection()
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    repository.save_analysis_report(build_payload())

    normalized_sql = [entry[0] for entry in connection.executed]
    assert normalized_sql[0] == " ".join(INSERT_ANALYSIS_REPORT_SQL.split())
    assert normalized_sql[1:5] == [" ".join(INSERT_ANALYSIS_MODULE_REPORT_SQL.split())] * 4
    assert normalized_sql[5:] == [" ".join(INSERT_ANALYSIS_SOURCE_SQL.split())] * 2
    assert connection.transaction_markers == ["begin", "end"]


def test_save_analysis_report_inserts_parent_four_modules_and_n_sources() -> None:
    connection = FakeConnection()
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    repository.save_analysis_report(build_payload())

    assert len(connection.executed) == 7
    report_rows = [entry for entry in connection.executed if entry[0] == " ".join(INSERT_ANALYSIS_REPORT_SQL.split())]
    module_rows = [entry for entry in connection.executed if entry[0] == " ".join(INSERT_ANALYSIS_MODULE_REPORT_SQL.split())]
    source_rows = [entry for entry in connection.executed if entry[0] == " ".join(INSERT_ANALYSIS_SOURCE_SQL.split())]
    assert len(report_rows) == 1
    assert len(module_rows) == 4
    assert len(source_rows) == 2


def test_save_analysis_report_returns_record_metadata() -> None:
    connection = FakeConnection()
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    result = repository.save_analysis_report(build_payload())

    assert result.record_id
    assert result.persisted_at.tzinfo is not None


def test_save_analysis_report_maps_key_payload_fields_to_sql_params() -> None:
    connection = FakeConnection()
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))
    payload = build_payload()

    repository.save_analysis_report(payload)

    report_params = connection.executed[0][1]
    first_module_params = connection.executed[1][1]

    assert report_params["ticker"] == "AAPL"
    assert report_params["request_id"] == "req_repo_123"
    assert report_params["overall_bias"] == payload.decision_synthesis.overall_bias.value
    assert report_params["actionability_state"] == payload.decision_synthesis.actionability_state.value
    assert report_params["market"] == payload.context.market
    assert first_module_params["module_name"] == "technical"
    assert first_module_params["status"] == payload.module_results.technical.status.value
    assert first_module_params["summary"] == payload.module_results.technical.summary

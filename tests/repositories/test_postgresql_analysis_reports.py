from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.graph.nodes.assemble_response import assemble_response
from app.graph.nodes.generate_trade_plan import generate_trade_plan
from app.graph.nodes.prepare_context import prepare_context
from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.graph.nodes.validate_request import validate_request
from app.repositories.analysis_reports import AnalysisReportPayload
from app.repositories.postgresql_analysis_reports import (
    INSERT_ANALYSIS_MODULE_REPORT_SQL,
    INSERT_ANALYSIS_REPORT_SQL,
    INSERT_ANALYSIS_SOURCE_SQL,
    PostgreSQLAnalysisReportRepository,
    SELECT_ANALYSIS_REPORT_BY_ID_SQL,
    SELECT_ANALYSIS_REPORTS_BY_TICKER_SQL,
    SELECT_LATEST_ANALYSIS_REPORT_BY_TICKER_SQL,
)
from app.rules.versions import MODULE_REPORT_SCHEMA_VERSION, PIPELINE_VERSION, STORAGE_SCHEMA_VERSION
from app.schemas.api import AnalysisResponse, Source, SourceType


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
                Source(type=SourceType.TECHNICAL, name="provider-a", url="https://example.com/a"),
                Source(type=SourceType.NEWS, name="provider-b", url="https://example.com/b"),
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
        module_reports=state.module_reports,
        decision_synthesis=state.decision_synthesis,
        trade_plan=state.trade_plan,
        response=state.response,
        sources=state.sources,
        diagnostics=state.diagnostics,
    )


class FakeCursor:
    def __init__(
        self,
        executed: list[tuple[str, dict[str, object], dict[str, Any]]],
        *,
        fetchone_result: dict[str, Any] | None = None,
        fetchall_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self.executed = executed
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []

    def execute(self, sql: str, params: dict[str, object]) -> None:
        self.executed.append((" ".join(sql.split()), params, {}))

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_result

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.fetchall_result)

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
    def __init__(
        self,
        *,
        fetchone_result: dict[str, Any] | None = None,
        fetchall_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self.executed: list[tuple[str, dict[str, object], dict[str, Any]]] = []
        self.transaction_markers: list[str] = []
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []

    def cursor(self, **kwargs: Any) -> FakeCursor:
        return FakeCursor(
            self.executed,
            fetchone_result=self.fetchone_result,
            fetchall_result=self.fetchall_result,
        )

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
    assert report_params["storage_schema_version"] == STORAGE_SCHEMA_VERSION
    assert report_params["pipeline_version"] == PIPELINE_VERSION
    assert first_module_params["module_name"] == "technical"
    assert first_module_params["report_schema_version"] == MODULE_REPORT_SCHEMA_VERSION
    assert first_module_params["status"] == payload.module_results.technical.status.value
    assert first_module_params["summary"] == payload.module_results.technical.summary
    assert report_params["diagnostics_json"].obj == payload.diagnostics.model_dump(mode="json")
    assert report_params["degraded_modules"].obj == payload.diagnostics.degraded_modules
    assert report_params["excluded_modules"].obj == payload.diagnostics.excluded_modules


def test_save_analysis_report_keeps_source_rows_aligned_with_response_sources() -> None:
    connection = FakeConnection()
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))
    payload = build_payload()

    repository.save_analysis_report(payload)

    source_rows = [
        params
        for sql, params, _ in connection.executed
        if sql == " ".join(INSERT_ANALYSIS_SOURCE_SQL.split())
    ]

    assert [source.name for source in payload.response.sources] == [source.name for source in payload.sources]
    assert [row["source_name"] for row in source_rows] == [source.name for source in payload.sources]
    assert [row["source_type"] for row in source_rows] == [source.type.value for source in payload.sources]
    assert [row["source_url"] for row in source_rows] == [str(source.url) for source in payload.sources]


def test_get_analysis_report_returns_mapped_report_or_none() -> None:
    payload = build_payload()
    connection = FakeConnection(fetchone_result=build_report_row(payload, report_id="report_1"))
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    report = repository.get_analysis_report("report_1")

    assert report is not None
    assert report.report_id == "report_1"
    assert report.normalized_ticker == "AAPL"
    assert report.response.ticker == "AAPL"
    assert connection.executed[0][0] == " ".join(SELECT_ANALYSIS_REPORT_BY_ID_SQL.split())
    assert connection.executed[0][1] == {"report_id": "report_1"}

    missing_repository = PostgreSQLAnalysisReportRepository(FakePool(FakeConnection()))
    assert missing_repository.get_analysis_report("missing") is None


def test_list_reports_by_ticker_applies_ticker_and_limit() -> None:
    payload = build_payload()
    rows = [
        build_report_row(payload, report_id="report_2"),
        build_report_row(
            payload,
            report_id="report_1",
            analysis_time=payload.analysis_time - timedelta(days=1),
        ),
    ]
    connection = FakeConnection(fetchall_result=rows)
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    reports = repository.list_reports_by_ticker("aapl", limit=5)

    assert [report.report_id for report in reports] == ["report_2", "report_1"]
    assert connection.executed[0][0] == " ".join(SELECT_ANALYSIS_REPORTS_BY_TICKER_SQL.split())
    assert connection.executed[0][1] == {"ticker": "AAPL", "limit": 5}


def test_get_latest_report_by_ticker_returns_latest_row_or_none() -> None:
    payload = build_payload()
    connection = FakeConnection(fetchone_result=build_report_row(payload, report_id="report_latest"))
    repository = PostgreSQLAnalysisReportRepository(FakePool(connection))

    report = repository.get_latest_report_by_ticker("aapl")

    assert report is not None
    assert report.report_id == "report_latest"
    assert connection.executed[0][0] == " ".join(SELECT_LATEST_ANALYSIS_REPORT_BY_TICKER_SQL.split())
    assert connection.executed[0][1] == {"ticker": "AAPL"}

    missing_repository = PostgreSQLAnalysisReportRepository(FakePool(FakeConnection()))
    assert missing_repository.get_latest_report_by_ticker("AAPL") is None


def build_report_row(
    payload: AnalysisReportPayload,
    *,
    report_id: str,
    analysis_time: datetime | None = None,
) -> dict[str, Any]:
    persisted_at = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    response = AnalysisResponse.model_validate(payload.response.model_dump(mode="json"))
    decision = payload.decision_synthesis.model_dump(mode="json")
    trade_plan = payload.trade_plan.model_dump(mode="json")
    return {
        "id": report_id,
        "request_id": payload.request_id,
        "ticker": payload.normalized_ticker,
        "raw_ticker": payload.raw_ticker,
        "analysis_time": analysis_time or payload.analysis_time,
        "overall_bias": payload.decision_synthesis.overall_bias.value,
        "actionability_state": payload.decision_synthesis.actionability_state.value,
        "response_json": response.model_dump(mode="json"),
        "decision_synthesis_json": decision,
        "trade_plan_json": trade_plan,
        "created_at": persisted_at,
        "updated_at": persisted_at,
    }

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.repositories.analysis_reports import (
    AnalysisReportPayload,
    PersistedAnalysisRecord,
    PersistedAnalysisReport,
)
from app.schemas.api import AnalysisResponse, DecisionSynthesis, TradePlan


STORAGE_SCHEMA_VERSION = "v1"
PIPELINE_VERSION = "langgraph-v1"
MODULE_REPORT_SCHEMA_VERSION = "v1"

INSERT_ANALYSIS_REPORT_SQL = """
INSERT INTO analysis_reports (
    id,
    request_id,
    storage_schema_version,
    pipeline_version,
    ticker,
    raw_ticker,
    market,
    analysis_time,
    request_payload_json,
    context_json,
    diagnostics_json,
    overall_bias,
    actionability_state,
    conflict_state,
    bias_score,
    confidence_score,
    data_completeness_pct,
    degraded_modules,
    excluded_modules,
    blocking_flags,
    decision_synthesis_json,
    trade_plan_json,
    response_json,
    created_at,
    updated_at
) VALUES (
    %(id)s,
    %(request_id)s,
    %(storage_schema_version)s,
    %(pipeline_version)s,
    %(ticker)s,
    %(raw_ticker)s,
    %(market)s,
    %(analysis_time)s,
    %(request_payload_json)s,
    %(context_json)s,
    %(diagnostics_json)s,
    %(overall_bias)s,
    %(actionability_state)s,
    %(conflict_state)s,
    %(bias_score)s,
    %(confidence_score)s,
    %(data_completeness_pct)s,
    %(degraded_modules)s,
    %(excluded_modules)s,
    %(blocking_flags)s,
    %(decision_synthesis_json)s,
    %(trade_plan_json)s,
    %(response_json)s,
    %(created_at)s,
    %(updated_at)s
)
""".strip()

INSERT_ANALYSIS_MODULE_REPORT_SQL = """
INSERT INTO analysis_module_reports (
    id,
    analysis_report_id,
    module_name,
    module_order,
    report_schema_version,
    status,
    direction,
    direction_value,
    data_completeness_pct,
    low_confidence,
    summary,
    risk_flags,
    report_json,
    created_at
) VALUES (
    %(id)s,
    %(analysis_report_id)s,
    %(module_name)s,
    %(module_order)s,
    %(report_schema_version)s,
    %(status)s,
    %(direction)s,
    %(direction_value)s,
    %(data_completeness_pct)s,
    %(low_confidence)s,
    %(summary)s,
    %(risk_flags)s,
    %(report_json)s,
    %(created_at)s
)
""".strip()

INSERT_ANALYSIS_SOURCE_SQL = """
INSERT INTO analysis_sources (
    id,
    analysis_report_id,
    source_type,
    source_name,
    source_url,
    fetched_at,
    created_at
) VALUES (
    %(id)s,
    %(analysis_report_id)s,
    %(source_type)s,
    %(source_name)s,
    %(source_url)s,
    %(fetched_at)s,
    %(created_at)s
)
""".strip()

SELECT_ANALYSIS_REPORT_BY_ID_SQL = """
SELECT
    id,
    request_id,
    ticker,
    raw_ticker,
    analysis_time,
    overall_bias,
    actionability_state,
    response_json,
    decision_synthesis_json,
    trade_plan_json,
    created_at,
    updated_at
FROM analysis_reports
WHERE id = %(report_id)s
""".strip()

SELECT_ANALYSIS_REPORTS_BY_TICKER_SQL = """
SELECT
    id,
    request_id,
    ticker,
    raw_ticker,
    analysis_time,
    overall_bias,
    actionability_state,
    response_json,
    decision_synthesis_json,
    trade_plan_json,
    created_at,
    updated_at
FROM analysis_reports
WHERE ticker = %(ticker)s
ORDER BY analysis_time DESC
LIMIT %(limit)s
""".strip()

SELECT_LATEST_ANALYSIS_REPORT_BY_TICKER_SQL = """
SELECT
    id,
    request_id,
    ticker,
    raw_ticker,
    analysis_time,
    overall_bias,
    actionability_state,
    response_json,
    decision_synthesis_json,
    trade_plan_json,
    created_at,
    updated_at
FROM analysis_reports
WHERE ticker = %(ticker)s
ORDER BY analysis_time DESC
LIMIT 1
""".strip()

MODULE_ORDER = {
    "technical": 1,
    "fundamental": 2,
    "sentiment": 3,
    "event": 4,
}


class PostgreSQLAnalysisReportRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        report_id = str(uuid4())
        persisted_at = datetime.now(UTC)
        module_rows = self._build_module_rows(payload, report_id, persisted_at)
        source_rows = self._build_source_rows(payload, report_id, persisted_at)

        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        INSERT_ANALYSIS_REPORT_SQL,
                        self._build_report_row(payload, report_id, persisted_at),
                    )

                    for row in module_rows:
                        cursor.execute(INSERT_ANALYSIS_MODULE_REPORT_SQL, row)

                    for row in source_rows:
                        cursor.execute(INSERT_ANALYSIS_SOURCE_SQL, row)

        return PersistedAnalysisRecord(record_id=report_id, persisted_at=persisted_at)

    def get_analysis_report(self, report_id: str) -> PersistedAnalysisReport | None:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    SELECT_ANALYSIS_REPORT_BY_ID_SQL,
                    {"report_id": report_id},
                )
                row = cursor.fetchone()

        return None if row is None else _map_persisted_report(row)

    def list_reports_by_ticker(
        self,
        ticker: str,
        limit: int = 20,
    ) -> list[PersistedAnalysisReport]:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    SELECT_ANALYSIS_REPORTS_BY_TICKER_SQL,
                    {"ticker": ticker.upper(), "limit": limit},
                )
                rows = cursor.fetchall()

        return [_map_persisted_report(row) for row in rows]

    def get_latest_report_by_ticker(self, ticker: str) -> PersistedAnalysisReport | None:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    SELECT_LATEST_ANALYSIS_REPORT_BY_TICKER_SQL,
                    {"ticker": ticker.upper()},
                )
                row = cursor.fetchone()

        return None if row is None else _map_persisted_report(row)

    def _build_report_row(
        self,
        payload: AnalysisReportPayload,
        report_id: str,
        persisted_at: datetime,
    ) -> dict[str, object]:
        decision = payload.decision_synthesis
        return {
            "id": report_id,
            "request_id": payload.request_id,
            "storage_schema_version": STORAGE_SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "ticker": payload.normalized_ticker,
            "raw_ticker": payload.raw_ticker,
            "market": payload.context.market,
            "analysis_time": payload.analysis_time,
            "request_payload_json": Jsonb(payload.request.model_dump(mode="json")),
            "context_json": Jsonb(payload.context.model_dump(mode="json")),
            "diagnostics_json": Jsonb(payload.diagnostics.model_dump(mode="json")),
            "overall_bias": decision.overall_bias.value,
            "actionability_state": decision.actionability_state.value,
            "conflict_state": decision.conflict_state.value,
            "bias_score": decision.bias_score,
            "confidence_score": decision.confidence_score,
            "data_completeness_pct": decision.data_completeness_pct,
            "degraded_modules": Jsonb(payload.diagnostics.degraded_modules),
            "excluded_modules": Jsonb(payload.diagnostics.excluded_modules),
            "blocking_flags": Jsonb(decision.blocking_flags),
            "decision_synthesis_json": Jsonb(decision.model_dump(mode="json")),
            "trade_plan_json": Jsonb(payload.trade_plan.model_dump(mode="json")),
            "response_json": Jsonb(payload.response.model_dump(mode="json")),
            "created_at": persisted_at,
            "updated_at": persisted_at,
        }

    def _build_module_rows(
        self,
        payload: AnalysisReportPayload,
        report_id: str,
        persisted_at: datetime,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []

        for module_name in ("technical", "fundamental", "sentiment", "event"):
            module_result = getattr(payload.module_results, module_name)
            if module_result is None:
                raise ValueError(f"module_results.{module_name} is required for persistence")

            rows.append(
                {
                    "id": str(uuid4()),
                    "analysis_report_id": report_id,
                    "module_name": module_name,
                    "module_order": MODULE_ORDER[module_name],
                    "report_schema_version": MODULE_REPORT_SCHEMA_VERSION,
                    "status": module_result.status.value,
                    "direction": module_result.direction.value if module_result.direction else None,
                    "direction_value": _direction_value(module_result.direction.value if module_result.direction else None),
                    "data_completeness_pct": module_result.data_completeness_pct,
                    "low_confidence": module_result.low_confidence,
                    "summary": module_result.summary,
                    "risk_flags": Jsonb(_module_risk_flags(module_result)),
                    "report_json": Jsonb(module_result.model_dump(mode="json")),
                    "created_at": persisted_at,
                }
            )

        return rows

    def _build_source_rows(
        self,
        payload: AnalysisReportPayload,
        report_id: str,
        persisted_at: datetime,
    ) -> list[dict[str, object]]:
        return [
            {
                "id": str(uuid4()),
                "analysis_report_id": report_id,
                "source_type": source.type.value,
                "source_name": source.name,
                "source_url": str(source.url),
                "fetched_at": None,
                "created_at": persisted_at,
            }
            for source in payload.sources
        ]


def _direction_value(direction: str | None) -> int | None:
    if direction == "bullish":
        return 1
    if direction in {"bearish", "disqualified"}:
        return -1
    if direction == "neutral":
        return 0
    return None


def _module_risk_flags(module_result) -> list[str]:
    flags: list[str] = []
    if module_result.reason:
        flags.append(module_result.reason)
    return flags


def _map_persisted_report(row: Mapping[str, Any]) -> PersistedAnalysisReport:
    return PersistedAnalysisReport(
        report_id=str(row["id"]),
        request_id=str(row["request_id"]),
        normalized_ticker=str(row["ticker"]),
        raw_ticker=str(row["raw_ticker"]),
        analysis_time=row["analysis_time"],
        overall_bias=str(row["overall_bias"]),
        actionability_state=str(row["actionability_state"]),
        response=AnalysisResponse.model_validate(row["response_json"]),
        decision_synthesis=DecisionSynthesis.model_validate(row["decision_synthesis_json"]),
        trade_plan=TradePlan.model_validate(row["trade_plan_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

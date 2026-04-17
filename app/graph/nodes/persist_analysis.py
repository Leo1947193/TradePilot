from __future__ import annotations

from app.repositories.analysis_reports import (
    AnalysisReportPayload,
    AnalysisReportRepository,
)
from app.schemas.graph_state import PersistenceState, PersistenceStatus, TradePilotState


def persist_analysis(
    state: TradePilotState | dict,
    repository: AnalysisReportRepository,
) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    if validated_state.response is None:
        raise ValueError("response is required to persist analysis")
    if validated_state.decision_synthesis is None:
        raise ValueError("decision_synthesis is required to persist analysis")
    if validated_state.trade_plan is None:
        raise ValueError("trade_plan is required to persist analysis")
    if not validated_state.normalized_ticker:
        raise ValueError("normalized_ticker is required to persist analysis")
    if validated_state.context.analysis_time is None:
        raise ValueError("context.analysis_time is required to persist analysis")

    payload = AnalysisReportPayload(
        request_id=validated_state.request_id,
        raw_ticker=validated_state.request.ticker,
        normalized_ticker=validated_state.normalized_ticker,
        analysis_time=validated_state.context.analysis_time,
        request=validated_state.request,
        context=validated_state.context,
        module_results=validated_state.module_results,
        decision_synthesis=validated_state.decision_synthesis,
        trade_plan=validated_state.trade_plan,
        response=validated_state.response,
        sources=validated_state.sources,
        diagnostics=validated_state.diagnostics,
    )

    try:
        persisted_record = repository.save_analysis_report(payload)
    except Exception as exc:
        validated_state.persistence = PersistenceState(
            status=PersistenceStatus.FAILED,
            record_id=None,
            persisted_at=None,
            error=str(exc),
        )
        raise RuntimeError("analysis report persistence failed") from exc

    return validated_state.model_copy(
        update={
            "persistence": PersistenceState(
                status=PersistenceStatus.SUCCEEDED,
                record_id=persisted_record.record_id,
                persisted_at=persisted_record.persisted_at,
                error=None,
            )
        }
    )

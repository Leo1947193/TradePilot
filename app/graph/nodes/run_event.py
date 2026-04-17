from __future__ import annotations

from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisModuleName, AnalysisModuleResult, ModuleExecutionStatus


EVENT_DEGRADED_SUMMARY = (
    "Event analysis is degraded because provider-backed company event and macro data is not available yet."
)
EVENT_DEGRADED_REASON = "event module placeholder until provider integration is implemented"
EVENT_DEGRADED_WARNING = (
    "Event analysis degraded: provider-backed company event and macro data is not available yet."
)


def run_event(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    event_result = AnalysisModuleResult(
        module=AnalysisModuleName.EVENT,
        status=ModuleExecutionStatus.DEGRADED,
        summary=EVENT_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=EVENT_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.EVENT.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.EVENT.value)

    warnings = list(validated_state.diagnostics.warnings)
    if EVENT_DEGRADED_WARNING not in warnings:
        warnings.append(EVENT_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"event": event_result}
    )
    updated_diagnostics = validated_state.diagnostics.model_copy(
        update={
            "degraded_modules": degraded_modules,
            "warnings": warnings,
        }
    )

    return validated_state.model_copy(
        update={
            "module_results": updated_module_results,
            "diagnostics": updated_diagnostics,
        }
    )

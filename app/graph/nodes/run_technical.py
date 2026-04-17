from __future__ import annotations

from app.schemas.graph_state import DiagnosticsState, ModuleResults, TradePilotState
from app.schemas.modules import AnalysisModuleName, AnalysisModuleResult, ModuleExecutionStatus


TECHNICAL_DEGRADED_SUMMARY = "Technical analysis is degraded because provider-backed market data is not available yet."
TECHNICAL_DEGRADED_REASON = "technical module placeholder until provider integration is implemented"
TECHNICAL_DEGRADED_WARNING = "Technical analysis degraded: provider-backed market data is not available yet."


def run_technical(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    technical_result = AnalysisModuleResult(
        module=AnalysisModuleName.TECHNICAL,
        status=ModuleExecutionStatus.DEGRADED,
        summary=TECHNICAL_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=TECHNICAL_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.TECHNICAL.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.TECHNICAL.value)

    warnings = list(validated_state.diagnostics.warnings)
    if TECHNICAL_DEGRADED_WARNING not in warnings:
        warnings.append(TECHNICAL_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"technical": technical_result}
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

from __future__ import annotations

from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisModuleName, AnalysisModuleResult, ModuleExecutionStatus


FUNDAMENTAL_DEGRADED_SUMMARY = (
    "Fundamental analysis is degraded because provider-backed financial data is not available yet."
)
FUNDAMENTAL_DEGRADED_REASON = (
    "fundamental module placeholder until provider integration is implemented"
)
FUNDAMENTAL_DEGRADED_WARNING = (
    "Fundamental analysis degraded: provider-backed financial data is not available yet."
)


def run_fundamental(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    fundamental_result = AnalysisModuleResult(
        module=AnalysisModuleName.FUNDAMENTAL,
        status=ModuleExecutionStatus.DEGRADED,
        summary=FUNDAMENTAL_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=FUNDAMENTAL_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.FUNDAMENTAL.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.FUNDAMENTAL.value)

    warnings = list(validated_state.diagnostics.warnings)
    if FUNDAMENTAL_DEGRADED_WARNING not in warnings:
        warnings.append(FUNDAMENTAL_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"fundamental": fundamental_result}
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

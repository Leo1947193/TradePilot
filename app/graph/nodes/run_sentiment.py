from __future__ import annotations

from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisModuleName, AnalysisModuleResult, ModuleExecutionStatus


SENTIMENT_DEGRADED_SUMMARY = (
    "Sentiment analysis is degraded because provider-backed news data is not available yet."
)
SENTIMENT_DEGRADED_REASON = (
    "sentiment module placeholder until provider integration is implemented"
)
SENTIMENT_DEGRADED_WARNING = (
    "Sentiment analysis degraded: provider-backed news data is not available yet."
)


def run_sentiment(state: TradePilotState | dict) -> TradePilotState:
    validated_state = TradePilotState.model_validate(state)

    sentiment_result = AnalysisModuleResult(
        module=AnalysisModuleName.SENTIMENT,
        status=ModuleExecutionStatus.DEGRADED,
        summary=SENTIMENT_DEGRADED_SUMMARY,
        direction=None,
        data_completeness_pct=None,
        low_confidence=True,
        reason=SENTIMENT_DEGRADED_REASON,
    )

    degraded_modules = list(validated_state.diagnostics.degraded_modules)
    if AnalysisModuleName.SENTIMENT.value not in degraded_modules:
        degraded_modules.append(AnalysisModuleName.SENTIMENT.value)

    warnings = list(validated_state.diagnostics.warnings)
    if SENTIMENT_DEGRADED_WARNING not in warnings:
        warnings.append(SENTIMENT_DEGRADED_WARNING)

    updated_module_results = validated_state.module_results.model_copy(
        update={"sentiment": sentiment_result}
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

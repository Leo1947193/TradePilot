from __future__ import annotations

from app.analysis.synthesis import build_decision_synthesis
from app.analysis.synthesis.adapt import adapt_module_signals
from app.schemas.api import ConflictState, Direction, FundamentalBias, ModuleName, ModuleStatus
from app.schemas.graph_state import ModuleResults


def test_adapt_module_signals_keeps_current_defaults_and_disqualified_mapping() -> None:
    module_results = ModuleResults.model_validate(
        {
            "fundamental": {
                "status": "usable",
                "direction": "disqualified",
                "reason": "Long thesis is not investable.",
            },
            "event": {
                "status": "degraded",
                "direction": "neutral",
            },
        }
    )

    signals = adapt_module_signals(module_results)

    assert [signal.module for signal in signals] == [
        ModuleName.TECHNICAL,
        ModuleName.FUNDAMENTAL,
        ModuleName.SENTIMENT,
        ModuleName.EVENT,
    ]
    assert signals[0].enabled is False
    assert signals[0].status == ModuleStatus.NOT_ENABLED
    assert signals[0].data_completeness_pct is None
    assert signals[1].enabled is True
    assert signals[1].direction == FundamentalBias.DISQUALIFIED
    assert signals[1].direction_value == -1
    assert signals[1].summary == "Long thesis is not investable."
    assert signals[3].status == ModuleStatus.DEGRADED
    assert signals[3].data_completeness_pct == 70.0


def test_build_decision_synthesis_preserves_current_weighting_and_risk_output() -> None:
    module_results = ModuleResults.model_validate(
        {
            "technical": {
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 90,
                "summary": "Trend remains constructive.",
            },
            "fundamental": {
                "status": "excluded",
                "direction": "bearish",
                "summary": "Coverage unavailable.",
            },
            "sentiment": {
                "status": "degraded",
                "direction": "neutral",
                "summary": "Signal coverage is partial.",
            },
            "event": {
                "status": "usable",
                "direction": "bearish",
                "data_completeness_pct": 100,
                "summary": "A material catalyst is near.",
            },
        }
    )

    decision = build_decision_synthesis(module_results)

    assert decision.overall_bias == Direction.BULLISH
    assert decision.bias_score == 0.33
    assert decision.conflict_state == ConflictState.MIXED
    assert decision.blocking_flags == ["event_risk_block"]
    assert decision.weight_scheme_used.enabled_modules == [
        ModuleName.TECHNICAL,
        ModuleName.FUNDAMENTAL,
        ModuleName.SENTIMENT,
        ModuleName.EVENT,
    ]
    assert decision.weight_scheme_used.available_weight_sum == 0.9
    assert decision.weight_scheme_used.available_weight_ratio == 0.9
    assert decision.weight_scheme_used.applied_weights.fundamental is None
    assert decision.module_contributions[1].status == ModuleStatus.EXCLUDED
    assert decision.module_contributions[1].data_completeness_pct == 0.0
    assert decision.module_contributions[2].status == ModuleStatus.DEGRADED
    assert decision.module_contributions[2].data_completeness_pct == 70.0
    assert decision.risks == ["降级模块较多：sentiment"]

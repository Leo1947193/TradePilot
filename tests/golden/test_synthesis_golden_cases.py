from __future__ import annotations

from collections.abc import Callable

from app.analysis.synthesis import build_decision_synthesis
from app.rules.messages import SYNTHESIS_INSUFFICIENT_EVIDENCE_RISK
from app.schemas.api import ConflictState, Direction, TechnicalSetupState
from app.schemas.graph_state import ModuleResults


def test_synthesis_golden_case_four_modules_aligned_bullish(
    make_module_results: Callable[..., ModuleResults],
) -> None:
    decision = build_decision_synthesis(
        make_module_results(
            technical={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 100,
                "summary": "Breakout remains intact.",
            },
            fundamental={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 100,
                "summary": "Earnings quality supports the long thesis.",
            },
            sentiment={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 100,
                "summary": "News tone keeps improving.",
            },
            event={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 100,
                "summary": "Catalysts remain supportive.",
            },
        )
    )

    assert decision.overall_bias == Direction.BULLISH
    assert decision.bias_score == 1.0
    assert decision.confidence_score == 1.0
    assert decision.actionability_state == TechnicalSetupState.ACTIONABLE
    assert decision.conflict_state == ConflictState.ALIGNED
    assert decision.blocking_flags == []
    assert decision.weight_scheme_used.available_weight_ratio == 1.0
    assert decision.weight_scheme_used.renormalized is False
    assert decision.risks == []


def test_synthesis_golden_case_technical_bullish_and_event_bearish_conflict(
    make_module_results: Callable[..., ModuleResults],
) -> None:
    decision = build_decision_synthesis(
        make_module_results(
            technical={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 95,
                "summary": "Trend and momentum remain constructive.",
            },
            fundamental={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 100,
                "summary": "Quality stays supportive.",
            },
            sentiment={
                "status": "usable",
                "direction": "neutral",
                "data_completeness_pct": 80,
                "summary": "Positioning is balanced.",
            },
            event={
                "status": "usable",
                "direction": "bearish",
                "data_completeness_pct": 100,
                "summary": "Near-term event risk skews negative.",
            },
        )
    )

    assert decision.overall_bias == Direction.BULLISH
    assert decision.bias_score == 0.4
    assert decision.conflict_state == ConflictState.MIXED
    assert decision.confidence_score == 0.72
    assert decision.actionability_state == TechnicalSetupState.AVOID
    assert decision.blocking_flags == ["event_risk_block"]
    assert decision.weight_scheme_used.available_weight_ratio == 1.0
    assert decision.risks == []


def test_synthesis_golden_case_available_weight_insufficient(
    make_module_results: Callable[..., ModuleResults],
) -> None:
    decision = build_decision_synthesis(
        make_module_results(
            technical={
                "status": "usable",
                "direction": "bullish",
                "data_completeness_pct": 90,
                "summary": "Technical evidence is still constructive.",
            },
            fundamental={
                "status": "excluded",
                "direction": "neutral",
                "summary": "Fundamental coverage is unavailable.",
            },
            sentiment={
                "status": "excluded",
                "direction": "neutral",
                "summary": "Sentiment coverage is unavailable.",
            },
            event=None,
        )
    )

    assert decision.overall_bias == Direction.BULLISH
    assert decision.bias_score == 1.0
    assert decision.conflict_state == ConflictState.ALIGNED
    assert decision.confidence_score == 0.79
    assert decision.actionability_state == TechnicalSetupState.ACTIONABLE
    assert decision.weight_scheme_used.enabled_modules == [
        "technical",
        "fundamental",
        "sentiment",
    ]
    assert decision.weight_scheme_used.disabled_modules == ["event"]
    assert decision.weight_scheme_used.available_weight_sum == 0.5
    assert decision.weight_scheme_used.available_weight_ratio == 0.625
    assert decision.weight_scheme_used.applied_weights.technical == 1.0
    assert decision.weight_scheme_used.renormalized is True
    assert decision.blocking_flags == []
    assert decision.risks == [SYNTHESIS_INSUFFICIENT_EVIDENCE_RISK]

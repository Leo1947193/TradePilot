from __future__ import annotations

from app.graph.nodes.run_event import run_event
from app.graph.nodes.run_fundamental import run_fundamental
from app.graph.nodes.run_sentiment import run_sentiment
from app.graph.nodes.run_technical import run_technical
from app.graph.nodes.synthesize_decision import synthesize_decision
from app.schemas.api import ConflictState, Direction, TechnicalSetupState


def build_placeholder_state() -> dict:
    return {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_123",
        "context": {
            "market": "US",
            "benchmark": "SPY",
            "analysis_window_days": [7, 90],
        },
    }


def test_synthesize_decision_writes_valid_public_decision_object() -> None:
    state = synthesize_decision(
        run_event(
            run_sentiment(
                run_fundamental(
                    run_technical(build_placeholder_state())
                )
            )
        )
    )

    assert state.decision_synthesis is not None
    assert state.decision_synthesis.overall_bias == Direction.NEUTRAL
    assert state.decision_synthesis.actionability_state == TechnicalSetupState.AVOID
    assert state.decision_synthesis.conflict_state == ConflictState.ALIGNED
    assert state.decision_synthesis.weight_scheme_used.enabled_modules == [
        "technical",
        "fundamental",
        "sentiment",
        "event",
    ]


def test_synthesize_decision_converts_four_degraded_modules_to_conservative_output() -> None:
    state = synthesize_decision(
        run_event(
            run_sentiment(
                run_fundamental(
                    run_technical(build_placeholder_state())
                )
            )
        )
    )

    assert state.decision_synthesis is not None
    assert state.decision_synthesis.overall_bias == "neutral"
    assert state.decision_synthesis.bias_score == 0.0
    assert state.decision_synthesis.confidence_score == 0.0
    assert state.decision_synthesis.actionability_state == "avoid"
    assert state.decision_synthesis.blocking_flags == []
    assert "当前仅有降级模块结果，综合结论不具备可执行性" in state.decision_synthesis.risks


def test_synthesize_decision_always_outputs_four_module_contributions() -> None:
    state = synthesize_decision(
        run_event(
            run_sentiment(
                run_fundamental(
                    run_technical(build_placeholder_state())
                )
            )
        )
    )

    assert state.decision_synthesis is not None
    assert len(state.decision_synthesis.module_contributions) == 4
    assert [item.module for item in state.decision_synthesis.module_contributions] == [
        "technical",
        "fundamental",
        "sentiment",
        "event",
    ]


def test_synthesize_decision_preserves_unrelated_state() -> None:
    input_state = build_placeholder_state()
    input_state["sources"] = [
        {
            "type": "technical",
            "name": "placeholder",
            "url": "https://example.com/source",
        }
    ]
    input_state["diagnostics"] = {
        "warnings": ["existing warning"],
    }

    state = synthesize_decision(
        run_event(
            run_sentiment(
                run_fundamental(
                    run_technical(input_state)
                )
            )
        )
    )

    assert state.request_id == "req_123"
    assert state.sources[0].name == "placeholder"
    assert state.diagnostics.warnings[0] == "existing warning"
    assert state.module_results.technical is not None

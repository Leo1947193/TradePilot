from __future__ import annotations

from collections.abc import Callable

import pytest


@pytest.fixture
def make_decision_payload() -> Callable[..., dict]:
    def _make_decision_payload(**overrides: object) -> dict:
        payload = {
            "overall_bias": "neutral",
            "bias_score": 0.0,
            "confidence_score": 0.0,
            "actionability_state": "avoid",
            "conflict_state": "aligned",
            "data_completeness_pct": 70.0,
            "weight_scheme_used": {
                "configured_weights": {
                    "technical": 0.5,
                    "fundamental": 0.1,
                    "sentiment": 0.2,
                    "event": 0.2,
                },
                "enabled_modules": ["technical", "fundamental", "sentiment", "event"],
                "disabled_modules": [],
                "enabled_weight_sum": 1.0,
                "available_weight_sum": 1.0,
                "available_weight_ratio": 1.0,
                "applied_weights": {
                    "technical": 0.5,
                    "fundamental": 0.1,
                    "sentiment": 0.2,
                    "event": 0.2,
                },
                "renormalized": False,
            },
            "blocking_flags": [],
            "module_contributions": [
                {
                    "module": "technical",
                    "enabled": True,
                    "status": "degraded",
                    "direction": "neutral",
                    "direction_value": 0,
                    "configured_weight": 0.5,
                    "applied_weight": 0.5,
                    "contribution": 0.0,
                    "data_completeness_pct": 70.0,
                    "low_confidence": True,
                },
                {
                    "module": "fundamental",
                    "enabled": True,
                    "status": "degraded",
                    "direction": "neutral",
                    "direction_value": 0,
                    "configured_weight": 0.1,
                    "applied_weight": 0.1,
                    "contribution": 0.0,
                    "data_completeness_pct": 70.0,
                    "low_confidence": True,
                },
                {
                    "module": "sentiment",
                    "enabled": True,
                    "status": "degraded",
                    "direction": "neutral",
                    "direction_value": 0,
                    "configured_weight": 0.2,
                    "applied_weight": 0.2,
                    "contribution": 0.0,
                    "data_completeness_pct": 70.0,
                    "low_confidence": True,
                },
                {
                    "module": "event",
                    "enabled": True,
                    "status": "degraded",
                    "direction": "neutral",
                    "direction_value": 0,
                    "configured_weight": 0.2,
                    "applied_weight": 0.2,
                    "contribution": 0.0,
                    "data_completeness_pct": 70.0,
                    "low_confidence": True,
                },
            ],
            "risks": ["Degraded modules keep the trade plan in a placeholder state."],
        }
        payload.update(overrides)
        return payload

    return _make_decision_payload

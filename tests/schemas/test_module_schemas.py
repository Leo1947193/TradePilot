from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.graph_state import TradePilotState
from app.schemas.modules import AnalysisModuleResult, ModuleExecutionStatus


def test_analysis_module_result_accepts_documented_enum_values() -> None:
    result = AnalysisModuleResult.model_validate(
        {
            "module": "technical",
            "status": "degraded",
            "summary": "Momentum data is partially stale.",
            "direction": "neutral",
            "data_completeness_pct": 82.5,
            "low_confidence": True,
            "reason": "volume history incomplete",
        }
    )

    assert result.module == "technical"
    assert result.status == ModuleExecutionStatus.DEGRADED
    assert result.direction == "neutral"
    assert result.low_confidence is True


def test_analysis_module_result_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisModuleResult.model_validate(
            {
                "module": "technical",
                "status": "partial",
            }
        )

    errors = exc_info.value.errors(include_url=False)
    assert errors[0]["loc"] == ("status",)
    assert errors[0]["type"] == "enum"


def test_analysis_module_result_enforces_data_completeness_bounds() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisModuleResult.model_validate(
            {
                "module": "event",
                "status": "usable",
                "data_completeness_pct": 120,
            }
        )

    errors = exc_info.value.errors(include_url=False)
    assert errors[0]["loc"] == ("data_completeness_pct",)
    assert errors[0]["type"] == "less_than_equal"


def test_trade_pilot_state_module_results_use_typed_internal_models() -> None:
    state = TradePilotState.model_validate(
        {
            "request": {"ticker": "AAPL"},
            "request_id": "req_123",
            "module_results": {
                "technical": {
                    "module": "technical",
                    "status": "usable",
                    "summary": "Trend remains constructive.",
                    "direction": "bullish",
                    "data_completeness_pct": 96,
                    "low_confidence": False,
                },
                "sentiment": {
                    "module": "sentiment",
                    "status": "excluded",
                    "summary": "News provider unavailable.",
                    "direction": "disqualified",
                    "reason": "provider outage",
                },
            },
        }
    )

    assert state.module_results.technical is not None
    assert state.module_results.technical.module == "technical"
    assert state.module_results.technical.status == ModuleExecutionStatus.USABLE
    assert state.module_results.sentiment is not None
    assert state.module_results.sentiment.reason == "provider outage"
    assert state.module_results.fundamental is None
    assert state.module_results.event is None

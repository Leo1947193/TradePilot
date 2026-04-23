from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "app" / "analysis" / "event" / "macro_sensitivity.py"
    spec = importlib.util.spec_from_file_location("tradepilot_macro_sensitivity", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


macro_sensitivity = _load_module()


def test_macro_sensitivity_flags_high_sensitivity_near_term_high_importance_event() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = macro_sensitivity.analyze_macro_sensitivity(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 30,
            "macro_sensitivity_context": {
                "sensitivity_level": "high",
                "style_tags": ["growth", "rates"],
            },
            "macro_events": [
                {
                    "event_name": "FOMC Rate Decision",
                    "category": "rates",
                    "scheduled_at": analysis_time + timedelta(days=2),
                    "importance": "high",
                    "source": {
                        "name": "macro-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                },
                {
                    "event_name": "Retail Sales",
                    "category": "consumption",
                    "scheduled_at": analysis_time + timedelta(days=10),
                    "importance": "medium",
                    "source": {
                        "name": "macro-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                },
            ],
        }
    )

    assert result.event_risk_flags == ["macro_event_high_sensitivity"]
    assert result.risk_events == ["FOMC Rate Decision"]
    assert result.macro_event_exposure == "high"
    assert len(result.records) == 2
    assert result.records[0].high_sensitivity is True
    assert result.low_confidence is False


def test_macro_sensitivity_does_not_flag_low_sensitivity_asset() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = macro_sensitivity.analyze_macro_sensitivity(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 30,
            "macro_sensitivity_context": {
                "sensitivity_level": "low",
            },
            "macro_events": [
                {
                    "event_name": "CPI",
                    "category": "inflation",
                    "scheduled_at": analysis_time + timedelta(days=3),
                    "importance": "high",
                    "source": {
                        "name": "macro-feed",
                        "fetched_at": analysis_time - timedelta(days=2),
                    },
                }
            ],
        }
    )

    assert result.event_risk_flags == []
    assert result.risk_events == []
    assert result.macro_event_exposure == "moderate"
    assert result.low_confidence is False


def test_macro_sensitivity_marks_missing_context_low_confidence() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = macro_sensitivity.analyze_macro_sensitivity(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 30,
            "macro_events": [
                {
                    "event_name": "Nonfarm Payrolls",
                    "category": "labor",
                    "scheduled_at": analysis_time + timedelta(days=5),
                    "importance": "high",
                    "source": {
                        "name": "macro-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                }
            ],
        }
    )

    assert result.event_risk_flags == []
    assert result.risk_events == []
    assert result.macro_event_exposure == "moderate"
    assert result.low_confidence is True

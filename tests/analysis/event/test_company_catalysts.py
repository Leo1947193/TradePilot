from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "app" / "analysis" / "event" / "company_catalysts.py"
    spec = importlib.util.spec_from_file_location("tradepilot_company_catalysts", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


company_catalysts = _load_module()


def test_company_catalysts_returns_bullish_for_confirmed_positive_catalyst() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = company_catalysts.analyze_company_catalysts(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 45,
            "company_catalyst_events": [
                {
                    "event_id": "launch-1",
                    "event_type": "launch",
                    "title": "Vision product launch",
                    "event_state": "confirmed",
                    "expected_date": analysis_time + timedelta(days=6),
                    "direction_hint": "positive",
                    "source": {
                        "name": "company-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                }
            ],
        }
    )

    assert result.upcoming_catalysts == ["Vision product launch"]
    assert result.confirmed_positive_catalysts == 1
    assert result.confirmed_negative_events == 0
    assert result.binary_event_count == 0
    assert result.event_risk_flags == []
    assert result.low_confidence is False


def test_company_catalysts_returns_bearish_for_confirmed_negative_catalyst() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = company_catalysts.analyze_company_catalysts(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 45,
            "company_catalyst_events": [
                {
                    "event_id": "recall-1",
                    "event_type": "recall",
                    "title": "Major recall announced",
                    "event_state": "confirmed",
                    "expected_date": analysis_time + timedelta(days=4),
                    "direction_hint": "negative",
                    "source": {
                        "name": "company-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                }
            ],
        }
    )

    assert result.risk_events == ["Major recall announced"]
    assert result.confirmed_negative_events == 1
    assert result.confirmed_positive_catalysts == 0
    assert result.low_confidence is False


def test_company_catalysts_marks_imminent_binary_event_as_risk_without_positive_override() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = company_catalysts.analyze_company_catalysts(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 30,
            "company_catalyst_events": [
                {
                    "event_id": "approval-1",
                    "event_type": "approval",
                    "title": "FDA approval decision",
                    "event_state": "pending",
                    "expected_date": analysis_time + timedelta(days=3),
                    "direction_hint": "binary",
                    "source": {
                        "name": "reg-feed",
                        "fetched_at": analysis_time - timedelta(days=2),
                    },
                }
            ],
        }
    )

    assert result.upcoming_catalysts == []
    assert result.binary_event_count == 1
    assert result.event_risk_flags == ["regulatory_decision_imminent"]
    assert result.risk_events == ["FDA approval decision"]
    assert result.low_confidence is False


def test_company_catalysts_keeps_rumor_as_background_only() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = company_catalysts.analyze_company_catalysts(
        {
            "analysis_time": analysis_time,
            "holding_horizon_days": 30,
            "company_catalyst_events": [
                {
                    "event_id": "rumor-1",
                    "event_type": "merger_rumor",
                    "title": "Merger rumor resurfaces",
                    "event_state": "rumored",
                    "expected_date": analysis_time + timedelta(days=12),
                    "direction_hint": "positive",
                    "source": {
                        "name": "news-feed",
                        "fetched_at": analysis_time - timedelta(days=1),
                    },
                }
            ],
        }
    )

    assert result.upcoming_catalysts == []
    assert result.risk_events == []
    assert result.event_risk_flags == []
    assert result.low_confidence is True
    assert result.records[0].event_state == "rumored"
    assert result.records[0].direction_hint == "positive"

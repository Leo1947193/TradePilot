from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[3] / "app/analysis/technical/patterns.py"
    spec = importlib.util.spec_from_file_location("worker3_patterns", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bar(index: int, close: float, *, high: float | None = None, low: float | None = None, volume: float = 1_000_000) -> dict[str, object]:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
    return {
        "timestamp": timestamp,
        "open": close,
        "high": high if high is not None else close + 0.8,
        "low": low if low is not None else close - 0.8,
        "close": close,
        "volume": volume,
    }


def test_analyze_patterns_prefers_vcp_over_flat_base_when_both_match() -> None:
    patterns = _load_module()
    closes = [
        100, 102, 104, 106, 109, 112, 115, 118,
        116, 114, 112, 113, 115, 116, 117, 118,
        116.5, 115.5, 115.0, 115.5, 116.0, 116.5, 117.0, 118.0,
    ]
    bars = []
    for idx, close in enumerate(closes):
        if idx < 8:
            volume = 2_400_000
        elif idx < 16:
            volume = 1_400_000
        else:
            volume = 800_000
        bars.append(_bar(idx, close, volume=volume))

    result = patterns.analyze_patterns(
        bars,
        multi_timeframe_result={"trend_daily": "bullish", "trend_weekly": "bullish", "ma_alignment": "fully_bullish"},
        momentum_result={"relative_strength": 1.15},
        volume_price_result={"obv_trend": "rising", "breakout_confirmed": True},
        atr_14=1.2,
    )

    assert result.pattern_detected == "vcp"
    assert result.pattern_direction == "bullish"
    assert result.pattern_quality == "high"
    assert result.risk_reward_ratio is not None and result.risk_reward_ratio > 1


def test_analyze_patterns_returns_none_path_when_no_shape_matches() -> None:
    patterns = _load_module()
    bars = [_bar(idx, 100 + ((-1) ** idx) * 3) for idx in range(20)]

    result = patterns.analyze_patterns(
        bars,
        multi_timeframe_result={"trend_daily": "neutral", "trend_weekly": "neutral"},
        momentum_result={"relative_strength": 1.0},
        volume_price_result={"obv_trend": "flat", "breakout_confirmed": False, "breakdown_confirmed": False},
        atr_14=None,
    )

    assert result.pattern_detected == "none"
    assert result.entry_trigger is None
    assert result.risk_reward_ratio is None
    assert result.low_confidence is True
    assert result.warnings == ("ATR unavailable; stop-loss and RR may be omitted",)

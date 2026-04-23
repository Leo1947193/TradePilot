from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[3] / "app/analysis/technical/volume_price.py"
    spec = importlib.util.spec_from_file_location("worker3_volume_price", module_path)
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


def test_analyze_volume_price_detects_bullish_divergence() -> None:
    volume_price = _load_module()
    closes = [100.0] * 70
    volumes = [1_000_000.0] * 70
    lows = [99.2] * 70
    highs = [100.8] * 70

    closes[20] = 95.0
    lows[20] = 94.0
    volumes[20] = 4_000_000.0
    closes[21:27] = [96.0, 97.5, 98.5, 99.0, 99.6, 100.2]
    for idx in range(21, 27):
        lows[idx] = closes[idx] - 0.7
        highs[idx] = closes[idx] + 0.9
        volumes[idx] = 1_700_000.0

    closes[39:44] = [98.5, 97.2, 96.0, 95.0, 94.6]
    for idx in range(39, 44):
        lows[idx] = closes[idx] - 0.8
        highs[idx] = closes[idx] + 0.8
        volumes[idx] = 900_000.0
    closes[44] = 94.2
    lows[44] = 93.5
    volumes[44] = 1_200_000.0

    for idx in range(45, 70):
        closes[idx] = 100.0 + (idx - 44) * 0.4
        lows[idx] = closes[idx] - 0.7
        highs[idx] = closes[idx] + 0.9
        volumes[idx] = 1_800_000.0

    bars = [
        _bar(idx, close, high=highs[idx], low=lows[idx], volume=volumes[idx])
        for idx, close in enumerate(closes)
    ]

    result = volume_price.analyze_volume_price(bars)

    assert result.obv_divergence == "bullish"
    assert result.obv_trend == "rising"
    assert result.volume_pattern == "accumulation"


def test_analyze_volume_price_enforces_breakout_breakdown_exclusivity_and_warns_on_short_history() -> None:
    volume_price = _load_module()
    bars = [_bar(idx, 100 + (idx * 0.1), volume=1_000_000) for idx in range(45)]
    bars[-3]["close"] = 104.0
    bars[-3]["high"] = 104.5
    bars[-2]["close"] = 106.0
    bars[-2]["high"] = 106.5
    bars[-1]["close"] = 108.0
    bars[-1]["high"] = 108.5
    bars[-1]["low"] = 96.0
    bars[-1]["volume"] = 2_600_000.0

    result = volume_price.analyze_volume_price(bars, key_support=[108.5], key_resistance=[105.0])

    assert result.breakout_confirmed is True
    assert result.breakdown_confirmed is False
    assert result.low_confidence is True
    assert result.warnings == ("volume-price lookback below 252 bars; using local breakout window",)

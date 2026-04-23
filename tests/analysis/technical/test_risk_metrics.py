from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[3] / "app/analysis/technical/risk_metrics.py"
    spec = importlib.util.spec_from_file_location("worker3_risk_metrics", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bar(index: int, close: float, *, high: float | None = None, low: float | None = None) -> dict[str, object]:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
    return {
        "timestamp": timestamp,
        "open": close,
        "high": high if high is not None else close * 1.03,
        "low": low if low is not None else close * 0.97,
        "close": close,
        "volume": 1_000_000.0,
    }


def test_analyze_risk_metrics_computes_beta_and_orders_flags_by_severity() -> None:
    risk_metrics = _load_module()
    benchmark_closes = [100.0]
    stock_closes = [100.0]
    for idx in range(1, 260):
        benchmark_return = 0.002 if idx % 2 == 0 else -0.001
        benchmark_closes.append(benchmark_closes[-1] * (1 + benchmark_return))
        stock_closes.append(stock_closes[-1] * (1 + benchmark_return * 2.8))

    daily_bars = [
        _bar(idx, close, high=close * 1.12, low=close * 0.88)
        for idx, close in enumerate(stock_closes)
    ]
    benchmark_bars = [_bar(idx, close) for idx, close in enumerate(benchmark_closes)]

    result = risk_metrics.analyze_risk_metrics(daily_bars, benchmark_bars=benchmark_bars, iv_inputs=2.8)

    assert result.beta is not None and result.beta > 2.0
    assert result.iv_vs_hv is not None and result.iv_vs_hv > 2.5
    assert result.risk_flags[0].startswith("extreme iv premium:")
    assert any(flag.startswith("high volatility:") for flag in result.risk_flags)
    assert any(flag.startswith("extreme beta:") for flag in result.risk_flags)


def test_analyze_risk_metrics_marks_iv_unavailable_without_blocking_other_metrics() -> None:
    risk_metrics = _load_module()
    closes = [100 + (idx * 0.2) for idx in range(80)]
    daily_bars = [_bar(idx, close) for idx, close in enumerate(closes)]

    result = risk_metrics.analyze_risk_metrics(daily_bars)

    assert result.iv_vs_hv is None
    assert result.beta is None
    assert result.max_drawdown_63d <= 0
    assert "IV data unavailable - options risk assessment degraded" in result.risk_flags
    assert "beta unavailable — SPY data missing" in result.warnings

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import log, sqrt


@dataclass(frozen=True)
class RiskMetricsResult:
    atr_14: float
    atr_pct: float
    beta: float | None
    bb_width: float
    bb_squeeze: bool
    max_drawdown_63d: float
    iv_vs_hv: float | None
    risk_flags: tuple[str, ...]
    data_completeness_pct: float
    low_confidence: bool
    warnings: tuple[str, ...] = ()


def analyze_risk_metrics(
    daily_bars: Sequence[object],
    *,
    benchmark_bars: Sequence[object] | None = None,
    iv_inputs: object | None = None,
) -> RiskMetricsResult:
    bars = list(daily_bars)
    _validate_bars(bars)

    closes = [_number(bar, "close") for bar in bars]
    atr_14 = calculate_atr_14(bars)
    atr_pct = (atr_14 / closes[-1]) * 100
    bb_width = calculate_bollinger_band_width(closes)
    bb_squeeze = detect_bollinger_squeeze(closes)
    max_drawdown_63d = calculate_max_drawdown_63d(closes)

    warnings: list[str] = []
    beta = None
    if benchmark_bars:
        beta = calculate_beta(bars, benchmark_bars)
        if beta is None:
            warnings.append("beta unavailable — insufficient aligned benchmark history")
    else:
        warnings.append("beta unavailable — SPY data missing")

    iv_vs_hv = None
    implied_volatility = _extract_implied_volatility(iv_inputs)
    if implied_volatility is None:
        warnings.append("IV data unavailable — options risk assessment degraded")
    else:
        iv_vs_hv = calculate_iv_vs_hv(closes, implied_volatility)

    risk_flags = build_risk_flags(
        atr_pct=atr_pct,
        beta=beta,
        bb_squeeze=bb_squeeze,
        max_drawdown_63d=max_drawdown_63d,
        iv_vs_hv=iv_vs_hv,
        iv_available=implied_volatility is not None,
    )

    available_metrics = 4
    if beta is not None:
        available_metrics += 1
    if iv_vs_hv is not None:
        available_metrics += 1
    data_completeness_pct = available_metrics / 6 * 100
    low_confidence = len(bars) < 126 or beta is None

    return RiskMetricsResult(
        atr_14=round(atr_14, 6),
        atr_pct=round(atr_pct, 4),
        beta=None if beta is None else round(beta, 4),
        bb_width=round(bb_width, 6),
        bb_squeeze=bb_squeeze,
        max_drawdown_63d=round(max_drawdown_63d, 6),
        iv_vs_hv=None if iv_vs_hv is None else round(iv_vs_hv, 4),
        risk_flags=risk_flags,
        data_completeness_pct=round(data_completeness_pct, 2),
        low_confidence=low_confidence,
        warnings=tuple(warnings),
    )


def calculate_atr_14(bars: Sequence[object]) -> float:
    if len(bars) < 14:
        raise ValueError("at least 14 bars are required for ATR")

    true_ranges: list[float] = []
    for idx, bar in enumerate(bars):
        high = _number(bar, "high")
        low = _number(bar, "low")
        if idx == 0:
            true_ranges.append(high - low)
            continue
        previous_close = _number(bars[idx - 1], "close")
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))

    atr = sum(true_ranges[:14]) / 14
    for tr in true_ranges[14:]:
        atr = ((atr * 13) + tr) / 14
    return atr


def calculate_bollinger_band_width(closes: Sequence[float]) -> float:
    if len(closes) < 20:
        raise ValueError("at least 20 closes are required for Bollinger band width")
    window = list(closes[-20:])
    sma = sum(window) / 20
    variance = sum((close - sma) ** 2 for close in window) / 20
    std_dev = sqrt(variance)
    upper = sma + (2 * std_dev)
    lower = sma - (2 * std_dev)
    return 0.0 if sma == 0 else (upper - lower) / sma


def detect_bollinger_squeeze(closes: Sequence[float]) -> bool:
    if len(closes) < 145:
        return False
    widths = [calculate_bollinger_band_width(closes[idx - 19 : idx + 1]) for idx in range(19, len(closes))]
    current = widths[-1]
    return current <= min(widths[-126:])


def calculate_max_drawdown_63d(closes: Sequence[float]) -> float:
    if len(closes) < 2:
        return 0.0
    window = list(closes[-63:])
    running_max = window[0]
    max_drawdown = 0.0
    for close in window:
        running_max = max(running_max, close)
        drawdown = (close - running_max) / running_max
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def calculate_beta(stock_bars: Sequence[object], benchmark_bars: Sequence[object]) -> float | None:
    stock_returns, benchmark_returns = _aligned_returns(stock_bars, benchmark_bars)
    if len(stock_returns) < 60 or len(benchmark_returns) < 60:
        return None
    mean_stock = sum(stock_returns) / len(stock_returns)
    mean_benchmark = sum(benchmark_returns) / len(benchmark_returns)
    covariance = sum(
        (stock - mean_stock) * (benchmark - mean_benchmark)
        for stock, benchmark in zip(stock_returns, benchmark_returns, strict=True)
    ) / len(stock_returns)
    variance = sum((value - mean_benchmark) ** 2 for value in benchmark_returns) / len(benchmark_returns)
    if variance == 0:
        return None
    return covariance / variance


def calculate_iv_vs_hv(closes: Sequence[float], implied_volatility: float) -> float:
    if len(closes) < 31:
        raise ValueError("at least 31 closes are required for historical volatility")
    log_returns = [log(closes[idx] / closes[idx - 1]) for idx in range(len(closes) - 29, len(closes))]
    mean_return = sum(log_returns) / len(log_returns)
    variance = sum((value - mean_return) ** 2 for value in log_returns) / len(log_returns)
    hv_30 = sqrt(variance) * sqrt(252)
    if hv_30 == 0:
        return 0.0
    return implied_volatility / hv_30


def build_risk_flags(
    *,
    atr_pct: float,
    beta: float | None,
    bb_squeeze: bool,
    max_drawdown_63d: float,
    iv_vs_hv: float | None,
    iv_available: bool,
) -> tuple[str, ...]:
    flags_by_bucket: dict[str, list[str]] = {"critical": [], "high": [], "medium": [], "info": []}

    if atr_pct > 8:
        flags_by_bucket["high"].append(f"high volatility: ATR {atr_pct:.1f}% of price")

    if beta is not None:
        if beta >= 2.5:
            flags_by_bucket["high"].append(
                f"extreme beta: {beta:.2f} vs SPY - loss amplification risk"
            )
        elif beta >= 1.5:
            flags_by_bucket["medium"].append(f"elevated beta: {beta:.2f} vs SPY")
        elif beta < 0:
            flags_by_bucket["medium"].append(f"anomalous negative beta: {beta:.2f}")

    drawdown_pct = abs(max_drawdown_63d) * 100
    if drawdown_pct > 30:
        flags_by_bucket["critical"].append(
            f"severe drawdown: {drawdown_pct:.1f}% in 63 days - avoid"
        )
    elif drawdown_pct > 20:
        flags_by_bucket["high"].append(f"deep drawdown: {drawdown_pct:.1f}% in 63 days")

    if iv_vs_hv is not None:
        if iv_vs_hv > 2.5:
            flags_by_bucket["critical"].append(
                f"extreme iv premium: {iv_vs_hv:.2f}x - jump risk extreme"
            )
        elif iv_vs_hv > 1.5:
            flags_by_bucket["high"].append(
                f"iv premium: implied vol {iv_vs_hv:.2f}x historical - jump risk elevated"
            )
    elif not iv_available:
        flags_by_bucket["info"].append("IV data unavailable - options risk assessment degraded")

    if bb_squeeze:
        flags_by_bucket["info"].append(
            "bollinger squeeze: volatility at 6-month low - breakout imminent"
        )

    ordered = (
        flags_by_bucket["critical"]
        + flags_by_bucket["high"]
        + flags_by_bucket["medium"]
        + flags_by_bucket["info"]
    )
    seen: set[str] = set()
    stable = []
    for flag in ordered:
        if flag not in seen:
            stable.append(flag)
            seen.add(flag)
    return tuple(stable)


def _aligned_returns(
    stock_bars: Sequence[object],
    benchmark_bars: Sequence[object],
) -> tuple[list[float], list[float]]:
    stock_by_timestamp = _bar_map(stock_bars)
    benchmark_by_timestamp = _bar_map(benchmark_bars)
    common_timestamps = sorted(set(stock_by_timestamp) & set(benchmark_by_timestamp))
    if len(common_timestamps) < 61:
        return [], []

    stock_closes = [stock_by_timestamp[timestamp] for timestamp in common_timestamps]
    benchmark_closes = [benchmark_by_timestamp[timestamp] for timestamp in common_timestamps]
    stock_returns = _close_to_returns(stock_closes)
    benchmark_returns = _close_to_returns(benchmark_closes)
    return stock_returns[-252:], benchmark_returns[-252:]


def _bar_map(bars: Sequence[object]) -> dict[object, float]:
    mapping: dict[object, float] = {}
    for idx, bar in enumerate(bars):
        timestamp = _field(bar, "timestamp", idx)
        mapping[timestamp] = _number(bar, "close")
    return mapping


def _close_to_returns(closes: Sequence[float]) -> list[float]:
    return [(closes[idx] - closes[idx - 1]) / closes[idx - 1] for idx in range(1, len(closes))]


def _extract_implied_volatility(iv_inputs: object | None) -> float | None:
    if iv_inputs is None:
        return None
    if isinstance(iv_inputs, (int, float)):
        return float(iv_inputs)
    if isinstance(iv_inputs, Sequence) and not isinstance(iv_inputs, (str, bytes)):
        values = [_extract_implied_volatility(item) for item in iv_inputs]
        filtered = [value for value in values if value is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)
    for field_name in ("implied_volatility", "iv"):
        value = _field(iv_inputs, field_name, None)
        if value is not None:
            return float(value)
    return None


def _validate_bars(bars: Sequence[object]) -> None:
    if len(bars) < 14:
        raise ValueError("at least 14 bars are required")
    for bar in bars:
        if _number(bar, "close") <= 0:
            raise ValueError("close must be positive")
        if _number(bar, "high") < _number(bar, "low"):
            raise ValueError("high must be >= low")


def _field(item: object, name: str, default: object | None = None) -> object | None:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _number(item: object, name: str) -> float:
    value = _field(item, name)
    if value is None:
        raise ValueError(f"missing numeric field: {name}")
    return float(value)

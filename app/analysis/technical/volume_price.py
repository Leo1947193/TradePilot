from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class VolumePriceResult:
    obv_trend: str
    obv_divergence: str
    breakout_confirmed: bool
    breakdown_confirmed: bool
    volume_pattern: str
    data_completeness_pct: float
    low_confidence: bool
    warnings: tuple[str, ...] = ()


def analyze_volume_price(
    daily_bars: Sequence[object],
    *,
    key_support: Sequence[float] | None = None,
    key_resistance: Sequence[float] | None = None,
) -> VolumePriceResult:
    bars = list(daily_bars)
    _validate_bars(bars)

    closes = [_number(bar, "close") for bar in bars]
    highs = [_number(bar, "high") for bar in bars]
    lows = [_number(bar, "low") for bar in bars]
    volumes = [_number(bar, "volume") for bar in bars]

    obv = calculate_obv(bars)
    obv_trend = classify_obv_trend(obv)
    obv_divergence = detect_obv_divergence(bars, obv)

    warnings: list[str] = []
    if len(bars) < 252:
        warnings.append("volume-price lookback below 252 bars; using local breakout window")

    avg_volume_20 = _average(volumes[-20:])
    breakout_confirmed, breakdown_confirmed = detect_breakout_breakdown(
        bars,
        average_volume_20=avg_volume_20,
        key_support=key_support,
        key_resistance=key_resistance,
    )

    up_volumes = [volumes[idx] for idx in range(1, len(bars)) if closes[idx] > closes[idx - 1]]
    down_volumes = [volumes[idx] for idx in range(1, len(bars)) if closes[idx] < closes[idx - 1]]
    avg_up_volume = _average(up_volumes[-20:]) if up_volumes else 0.0
    avg_down_volume = _average(down_volumes[-20:]) if down_volumes else 0.0

    last_close = closes[-1]
    previous_close = closes[-2]
    last_volume = volumes[-1]

    volume_pattern = "neutral"
    if (
        obv_trend == "rising"
        and avg_up_volume > avg_down_volume * 1.2
        and not breakdown_confirmed
    ):
        volume_pattern = "accumulation"
    elif (
        obv_trend == "falling"
        and avg_down_volume > avg_up_volume * 1.2
        and not breakout_confirmed
    ):
        volume_pattern = "distribution"
    elif obv_trend == "rising" and last_close < previous_close and last_volume < avg_volume_20 * 0.8:
        volume_pattern = "pullback_healthy"
    elif obv_trend == "falling" and last_close > previous_close and last_volume < avg_volume_20 * 0.8:
        volume_pattern = "bounce_weak"

    data_completeness_pct = min(len(bars), 252) / 252 * 100
    low_confidence = len(bars) < 40 or bool(warnings)

    return VolumePriceResult(
        obv_trend=obv_trend,
        obv_divergence=obv_divergence,
        breakout_confirmed=breakout_confirmed,
        breakdown_confirmed=breakdown_confirmed,
        volume_pattern=volume_pattern,
        data_completeness_pct=round(data_completeness_pct, 2),
        low_confidence=low_confidence,
        warnings=tuple(warnings),
    )


def calculate_obv(bars: Sequence[object]) -> list[float]:
    if not bars:
        return []

    closes = [_number(bar, "close") for bar in bars]
    volumes = [_number(bar, "volume") for bar in bars]
    obv = [0.0]

    for idx in range(1, len(bars)):
        prior = obv[-1]
        if volumes[idx] == 0:
            obv.append(prior)
        elif closes[idx] > closes[idx - 1]:
            obv.append(prior + volumes[idx])
        elif closes[idx] < closes[idx - 1]:
            obv.append(prior - volumes[idx])
        else:
            obv.append(prior)

    return obv


def classify_obv_trend(obv: Sequence[float]) -> str:
    if len(obv) < 40:
        return "flat"

    obv_sma = _rolling_average(obv, 20)
    tail = obv_sma[-20:]
    if len(tail) < 20:
        return "flat"

    slope = _linear_regression_slope(tail)
    reference = abs(_average(tail)) or abs(tail[-1]) or 1.0
    normalized_slope = slope / reference

    if normalized_slope >= 0.001:
        return "rising"
    if normalized_slope <= -0.001:
        return "falling"
    return "flat"


def detect_obv_divergence(bars: Sequence[object], obv: Sequence[float]) -> str:
    if len(bars) < 60 or len(obv) != len(bars):
        return "none"

    recent_bars = list(bars[-60:])
    recent_obv = list(obv[-60:])
    lows = [_number(bar, "low") for bar in recent_bars]
    highs = [_number(bar, "high") for bar in recent_bars]

    price_low_pivots = _find_local_pivots(lows, kind="low")
    price_high_pivots = _find_local_pivots(highs, kind="high")
    obv_low_pivots = _find_local_pivots(recent_obv, kind="low")
    obv_high_pivots = _find_local_pivots(recent_obv, kind="high")

    bullish = _check_bullish_divergence(price_low_pivots, obv_low_pivots, lows, recent_obv)
    bearish = _check_bearish_divergence(price_high_pivots, obv_high_pivots, highs, recent_obv)

    if bullish and bearish:
        return "bullish" if bullish[0] >= bearish[0] else "bearish"
    if bullish:
        return "bullish"
    if bearish:
        return "bearish"
    return "none"


def detect_breakout_breakdown(
    bars: Sequence[object],
    *,
    average_volume_20: float,
    key_support: Sequence[float] | None = None,
    key_resistance: Sequence[float] | None = None,
) -> tuple[bool, bool]:
    if len(bars) < 3:
        return False, False

    closes = [_number(bar, "close") for bar in bars]
    highs = [_number(bar, "high") for bar in bars]
    lows = [_number(bar, "low") for bar in bars]
    volumes = [_number(bar, "volume") for bar in bars]

    prior_high = max(highs[:-1])
    prior_low = min(lows[:-1])
    resistance = min([value for value in [prior_high, *(key_resistance or [])] if value is not None])
    support = max([value for value in [prior_low, *(key_support or [])] if value is not None])

    breakout = (
        closes[-1] > resistance
        and volumes[-1] >= average_volume_20 * 1.5
        and sum(close > resistance for close in closes[-3:]) >= 2
    )
    breakdown = (
        closes[-1] < support
        and volumes[-1] >= average_volume_20 * 1.5
        and sum(close < support for close in closes[-3:]) >= 2
    )

    if breakout and breakdown:
        if closes[-1] >= closes[-2]:
            return True, False
        return False, True

    return breakout, breakdown


def _check_bullish_divergence(
    price_pivots: Sequence[int],
    obv_pivots: Sequence[int],
    lows: Sequence[float],
    obv: Sequence[float],
) -> tuple[int, int] | None:
    for left, right in _pivot_pairs(price_pivots):
        if lows[right] >= lows[left] * 0.995:
            continue
        aligned_left = _nearest_pivot(obv_pivots, left)
        aligned_right = _nearest_pivot(obv_pivots, right)
        if aligned_left is None or aligned_right is None:
            continue
        if abs(aligned_left - left) > 5 or abs(aligned_right - right) > 5:
            continue
        if obv[aligned_right] > obv[aligned_left]:
            return right, aligned_right
    return None


def _check_bearish_divergence(
    price_pivots: Sequence[int],
    obv_pivots: Sequence[int],
    highs: Sequence[float],
    obv: Sequence[float],
) -> tuple[int, int] | None:
    for left, right in _pivot_pairs(price_pivots):
        if highs[right] <= highs[left] * 1.005:
            continue
        aligned_left = _nearest_pivot(obv_pivots, left)
        aligned_right = _nearest_pivot(obv_pivots, right)
        if aligned_left is None or aligned_right is None:
            continue
        if abs(aligned_left - left) > 5 or abs(aligned_right - right) > 5:
            continue
        if obv[aligned_right] < obv[aligned_left]:
            return right, aligned_right
    return None


def _pivot_pairs(pivots: Sequence[int]) -> list[tuple[int, int]]:
    if len(pivots) < 2:
        return []
    return [(pivots[idx - 1], pivots[idx]) for idx in range(1, len(pivots))]


def _nearest_pivot(pivots: Sequence[int], target: int) -> int | None:
    if not pivots:
        return None
    return min(pivots, key=lambda pivot: abs(pivot - target))


def _find_local_pivots(values: Sequence[float], *, kind: str, radius: int = 5) -> list[int]:
    pivots: list[int] = []
    for idx in range(radius, len(values) - radius):
        window = values[idx - radius : idx + radius + 1]
        current = values[idx]
        if kind == "low" and current == min(window) and window.count(current) == 1:
            pivots.append(idx)
        if kind == "high" and current == max(window) and window.count(current) == 1:
            pivots.append(idx)
    return pivots


def _rolling_average(values: Sequence[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        return []
    return [_average(values[idx - period + 1 : idx + 1]) for idx in range(period - 1, len(values))]


def _linear_regression_slope(values: Sequence[float]) -> float:
    count = len(values)
    x_mean = (count - 1) / 2
    y_mean = _average(values)
    numerator = sum((idx - x_mean) * (value - y_mean) for idx, value in enumerate(values))
    denominator = sum((idx - x_mean) ** 2 for idx in range(count))
    if isclose(denominator, 0.0):
        return 0.0
    return numerator / denominator


def _validate_bars(bars: Sequence[object]) -> None:
    if len(bars) < 3:
        raise ValueError("at least 3 bars are required")

    for bar in bars:
        if _number(bar, "high") < _number(bar, "low"):
            raise ValueError("bar high must be >= low")
        if _number(bar, "close") <= 0:
            raise ValueError("bar close must be positive")


def _number(item: object, name: str) -> float:
    if isinstance(item, Mapping):
        value = item[name]
    else:
        value = getattr(item, name)
    return float(value)


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternMatch:
    pattern_detected: str
    pattern_direction: str
    pattern_quality: str
    entry_trigger: float | None
    target_price: float | None
    stop_loss_price: float | None
    risk_reward_ratio: float | None
    priority: int


@dataclass(frozen=True)
class PatternRecognitionResult:
    pattern_direction: str
    pattern_detected: str
    pattern_quality: str
    entry_trigger: float | None
    target_price: float | None
    stop_loss_price: float | None
    risk_reward_ratio: float | None
    data_completeness_pct: float
    low_confidence: bool
    warnings: tuple[str, ...] = ()


def analyze_patterns(
    daily_bars: Sequence[object],
    *,
    multi_timeframe_result: object,
    momentum_result: object,
    volume_price_result: object,
    atr_14: float | None = None,
) -> PatternRecognitionResult:
    bars = list(daily_bars)
    _validate_bars(bars)

    warnings: list[str] = []
    matches = [
        detect_vcp(
            bars,
            multi_timeframe_result=multi_timeframe_result,
            momentum_result=momentum_result,
            volume_price_result=volume_price_result,
            atr_14=atr_14,
        ),
        detect_bull_flag(
            bars,
            multi_timeframe_result=multi_timeframe_result,
            momentum_result=momentum_result,
            volume_price_result=volume_price_result,
            atr_14=atr_14,
        ),
        detect_flat_base(
            bars,
            multi_timeframe_result=multi_timeframe_result,
            momentum_result=momentum_result,
            volume_price_result=volume_price_result,
            atr_14=atr_14,
        ),
        detect_bear_flag(
            bars,
            multi_timeframe_result=multi_timeframe_result,
            momentum_result=momentum_result,
            volume_price_result=volume_price_result,
            atr_14=atr_14,
        ),
    ]

    candidates = [match for match in matches if match is not None]
    data_completeness_pct = min(len(bars), 60) / 60 * 100
    low_confidence = len(bars) < 20 or atr_14 is None
    if atr_14 is None:
        warnings.append("ATR unavailable; stop-loss and RR may be omitted")

    if not candidates:
        return PatternRecognitionResult(
            pattern_direction="neutral",
            pattern_detected="none",
            pattern_quality="low",
            entry_trigger=None,
            target_price=None,
            stop_loss_price=None,
            risk_reward_ratio=None,
            data_completeness_pct=round(data_completeness_pct, 2),
            low_confidence=low_confidence,
            warnings=tuple(warnings),
        )

    selected = select_best_pattern(candidates)
    return PatternRecognitionResult(
        pattern_direction=selected.pattern_direction,
        pattern_detected=selected.pattern_detected,
        pattern_quality=selected.pattern_quality,
        entry_trigger=selected.entry_trigger,
        target_price=selected.target_price,
        stop_loss_price=selected.stop_loss_price,
        risk_reward_ratio=selected.risk_reward_ratio,
        data_completeness_pct=round(data_completeness_pct, 2),
        low_confidence=low_confidence,
        warnings=tuple(warnings),
    )


def detect_vcp(
    bars: Sequence[object],
    *,
    multi_timeframe_result: object,
    momentum_result: object,
    volume_price_result: object,
    atr_14: float | None,
) -> PatternMatch | None:
    if _field(multi_timeframe_result, "trend_daily") != "bullish":
        return None
    if _field(momentum_result, "relative_strength", 0.0) < 1.0:
        return None
    if _field(volume_price_result, "obv_trend") == "falling":
        return None

    closes = [_number(bar, "close") for bar in bars[-24:]]
    highs = [_number(bar, "high") for bar in bars[-24:]]
    lows = [_number(bar, "low") for bar in bars[-24:]]
    volumes = [_number(bar, "volume") for bar in bars[-24:]]
    if len(closes) < 18:
        return None

    segments = [slice(0, 8), slice(8, 16), slice(16, 24)]
    ranges = [max(highs[segment]) - min(lows[segment]) for segment in segments]
    if not (ranges[1] < ranges[0] * 0.9 and ranges[2] < ranges[1] * 0.9):
        return None

    pivot_high = max(highs[-12:])
    if max(highs[-6:]) < pivot_high * 0.985:
        return None

    avg_recent_volume = _average(volumes[-6:])
    avg_prior_volume = _average(volumes[-18:-6])
    if avg_recent_volume >= avg_prior_volume * 0.8:
        return None

    return _build_bullish_match(
        "vcp",
        "high" if _field(volume_price_result, "breakout_confirmed", False) else "medium",
        entry_trigger=pivot_high,
        base_low=min(lows[-6:]),
        base_height=max(closes) - min(closes[:8]),
        atr_14=atr_14,
        priority=4,
    )


def detect_bull_flag(
    bars: Sequence[object],
    *,
    multi_timeframe_result: object,
    momentum_result: object,
    volume_price_result: object,
    atr_14: float | None,
) -> PatternMatch | None:
    if _field(multi_timeframe_result, "trend_daily") != "bullish":
        return None
    if _field(momentum_result, "relative_strength", 0.0) < 0.8:
        return None

    closes = [_number(bar, "close") for bar in bars]
    highs = [_number(bar, "high") for bar in bars]
    lows = [_number(bar, "low") for bar in bars]
    volumes = [_number(bar, "volume") for bar in bars]
    if len(closes) < 15:
        return None

    pole = closes[-11] - closes[-16]
    if pole / closes[-16] < 0.1:
        return None

    flag_closes = closes[-10:]
    if flag_closes[-1] > flag_closes[0]:
        return None
    retracement = (max(flag_closes) - min(flag_closes)) / pole if pole else 0.0
    if retracement > 0.45:
        return None

    avg_flag_volume = _average(volumes[-10:])
    avg_pole_volume = _average(volumes[-16:-10])
    if avg_flag_volume >= avg_pole_volume * 0.9:
        return None

    quality = "high" if _field(volume_price_result, "breakout_confirmed", False) else "medium"
    return _build_bullish_match(
        "bull_flag",
        quality,
        entry_trigger=max(highs[-10:]),
        base_low=min(lows[-10:]),
        base_height=pole,
        atr_14=atr_14,
        priority=3,
    )


def detect_flat_base(
    bars: Sequence[object],
    *,
    multi_timeframe_result: object,
    momentum_result: object,
    volume_price_result: object,
    atr_14: float | None,
) -> PatternMatch | None:
    if _field(multi_timeframe_result, "trend_daily") != "bullish":
        return None
    if _field(multi_timeframe_result, "trend_weekly", "neutral") not in {"bullish", "neutral"}:
        return None
    if _field(momentum_result, "relative_strength", 0.0) < 1.0:
        return None
    if _field(volume_price_result, "obv_trend", "flat") == "falling":
        return None

    closes = [_number(bar, "close") for bar in bars[-20:]]
    highs = [_number(bar, "high") for bar in bars[-20:]]
    lows = [_number(bar, "low") for bar in bars[-20:]]
    if len(closes) < 15:
        return None

    platform_high = max(closes)
    platform_low = min(closes)
    if platform_low <= 0:
        return None
    amplitude = (platform_high - platform_low) / platform_high
    if amplitude > 0.15:
        return None

    return _build_bullish_match(
        "flat_base",
        "high" if _field(volume_price_result, "breakout_confirmed", False) else "medium",
        entry_trigger=max(highs),
        base_low=min(lows),
        base_height=platform_high - platform_low,
        atr_14=atr_14,
        priority=2,
    )


def detect_bear_flag(
    bars: Sequence[object],
    *,
    multi_timeframe_result: object,
    momentum_result: object,
    volume_price_result: object,
    atr_14: float | None,
) -> PatternMatch | None:
    if _field(multi_timeframe_result, "trend_daily") != "bearish":
        return None
    if _field(momentum_result, "relative_strength", 1.0) > 1.0:
        return None

    closes = [_number(bar, "close") for bar in bars]
    highs = [_number(bar, "high") for bar in bars]
    lows = [_number(bar, "low") for bar in bars]
    volumes = [_number(bar, "volume") for bar in bars]
    if len(closes) < 15:
        return None

    pole = closes[-16] - closes[-11]
    if pole / closes[-16] < 0.1:
        return None

    flag_closes = closes[-10:]
    if flag_closes[-1] < flag_closes[0]:
        return None
    retracement = (max(flag_closes) - min(flag_closes)) / pole if pole else 0.0
    if retracement > 0.45:
        return None

    avg_flag_volume = _average(volumes[-10:])
    avg_pole_volume = _average(volumes[-16:-10])
    if avg_flag_volume >= avg_pole_volume * 0.9:
        return None

    entry_trigger = min(lows[-10:])
    stop = max(highs[-10:]) + (atr_14 or 0.0)
    target = entry_trigger - pole
    rr = _risk_reward(entry_trigger, target, stop)
    quality = "high" if _field(volume_price_result, "breakdown_confirmed", False) else "medium"
    return PatternMatch(
        pattern_detected="bear_flag",
        pattern_direction="bearish",
        pattern_quality=quality,
        entry_trigger=entry_trigger,
        target_price=target,
        stop_loss_price=stop if atr_14 is not None else None,
        risk_reward_ratio=rr,
        priority=3,
    )


def select_best_pattern(matches: Sequence[PatternMatch]) -> PatternMatch:
    quality_score = {"low": 1, "medium": 2, "high": 3}
    return max(
        matches,
        key=lambda match: (
            quality_score.get(match.pattern_quality, 0),
            match.risk_reward_ratio is not None,
            match.priority,
        ),
    )


def _build_bullish_match(
    pattern_detected: str,
    quality: str,
    *,
    entry_trigger: float,
    base_low: float,
    base_height: float,
    atr_14: float | None,
    priority: int,
) -> PatternMatch:
    stop = None if atr_14 is None else base_low - atr_14
    target = entry_trigger + base_height
    rr = _risk_reward(entry_trigger, target, stop)
    return PatternMatch(
        pattern_detected=pattern_detected,
        pattern_direction="bullish",
        pattern_quality=quality,
        entry_trigger=entry_trigger,
        target_price=target,
        stop_loss_price=stop,
        risk_reward_ratio=rr,
        priority=priority,
    )


def _risk_reward(
    entry_trigger: float | None,
    target_price: float | None,
    stop_loss_price: float | None,
) -> float | None:
    if entry_trigger is None or target_price is None or stop_loss_price is None:
        return None
    risk = entry_trigger - stop_loss_price
    reward = target_price - entry_trigger
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _validate_bars(bars: Sequence[object]) -> None:
    if len(bars) < 10:
        raise ValueError("at least 10 bars are required")
    for bar in bars:
        if _number(bar, "close") <= 0:
            raise ValueError("close must be positive")


def _field(item: object, name: str, default: object | None = None) -> object | None:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _number(item: object, name: str) -> float:
    value = _field(item, name)
    if value is None:
        raise ValueError(f"missing numeric field: {name}")
    return float(value)


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0

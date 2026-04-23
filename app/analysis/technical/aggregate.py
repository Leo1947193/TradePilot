from __future__ import annotations

from statistics import fmean

from app.analysis.technical.momentum import MomentumResult
from app.analysis.technical.multi_timeframe import MultiTimeframeResult
from app.analysis.technical.patterns import PatternRecognitionResult
from app.analysis.technical.risk_metrics import RiskMetricsResult
from app.analysis.technical.schemas import (
    TechnicalAggregateResult,
    TechnicalSignal,
    TechnicalSubmoduleBundle,
)
from app.analysis.technical.volume_price import VolumePriceResult
from app.schemas.api import TechnicalSetupState, VolumePattern
from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import MarketBar


def analyze_market_bars(bars: list[MarketBar]) -> TechnicalSignal:
    bar_count = len(bars)
    first_close = bars[0].close
    last_close = bars[-1].close
    price_return_pct = ((last_close - first_close) / first_close) * 100 if first_close else 0.0

    moving_window = bars[-min(bar_count, 20) :]
    moving_average = sum(bar.close for bar in moving_window) / len(moving_window)

    if price_return_pct >= 3 and last_close >= moving_average:
        direction = AnalysisDirection.BULLISH
        trend_label = "above"
    elif price_return_pct <= -3 and last_close <= moving_average:
        direction = AnalysisDirection.BEARISH
        trend_label = "below"
    else:
        direction = AnalysisDirection.NEUTRAL
        trend_label = "near"

    low_confidence = bar_count < 5 and direction == AnalysisDirection.NEUTRAL
    data_completeness_pct = min(bar_count, 60) / 60 * 100
    summary = (
        f"Technical analysis reviewed {bar_count} market bars. "
        f"Price return over lookback: {price_return_pct:+.2f}%. "
        f"Latest close is {trend_label} the short moving average, producing a "
        f"{direction.value} bias."
    )

    return TechnicalSignal(
        direction=direction,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )


def aggregate_technical_signals(
    *,
    daily_signal: TechnicalSignal,
    submodules: TechnicalSubmoduleBundle | None = None,
) -> TechnicalAggregateResult:
    if submodules is None:
        setup_state = _resolve_setup_state(
            direction=daily_signal.direction,
            low_confidence=daily_signal.low_confidence,
        )

        return TechnicalAggregateResult(
            technical_signal=daily_signal.direction,
            trend=daily_signal.direction,
            setup_state=setup_state,
            summary=daily_signal.summary,
            data_completeness_pct=daily_signal.data_completeness_pct,
            low_confidence=daily_signal.low_confidence,
            risk_flags=_build_risk_flags(
                direction=daily_signal.direction,
                low_confidence=daily_signal.low_confidence,
            ),
            key_support=[],
            key_resistance=[],
            volume_pattern=VolumePattern.NEUTRAL,
            entry_trigger=None,
            target_price=None,
            stop_loss_price=None,
            risk_reward_ratio=None,
            subsignals={"daily_bars": daily_signal},
        )

    structure_signal = _resolve_structure_signal(submodules.multi_timeframe)
    momentum_signal = _resolve_momentum_signal(submodules.momentum)
    volume_signal = _resolve_volume_signal(submodules.volume_price)
    pattern_signal = _resolve_pattern_signal(submodules.patterns)
    adx_confidence = _resolve_adx_confidence(submodules.momentum.adx)
    technical_signal = _resolve_technical_signal(
        structure_signal=structure_signal,
        momentum_signal=momentum_signal,
        volume_signal=volume_signal,
        pattern_signal=pattern_signal,
        adx_confidence=adx_confidence,
    )
    trend = structure_signal
    risk_flags = _merge_risk_flags(
        submodules.risk_metrics.risk_flags,
        direction=technical_signal,
        low_confidence=(
            daily_signal.low_confidence
            or submodules.multi_timeframe.low_confidence
            or submodules.momentum.low_confidence
            or submodules.volume_price.low_confidence
            or submodules.risk_metrics.low_confidence
            or submodules.patterns.low_confidence
        ),
    )
    setup_state = _resolve_rich_setup_state(
        technical_signal=technical_signal,
        submodules=submodules,
        risk_flags=risk_flags,
        structure_signal=structure_signal,
        momentum_signal=momentum_signal,
        volume_signal=volume_signal,
        pattern_signal=pattern_signal,
    )
    entry_trigger = _format_entry_trigger(submodules.patterns)
    summary = _build_rich_summary(
        technical_signal=technical_signal,
        trend=trend,
        setup_state=setup_state,
        submodules=submodules,
        risk_flags=risk_flags,
        entry_trigger=entry_trigger,
    )

    return TechnicalAggregateResult(
        technical_signal=technical_signal,
        trend=trend,
        setup_state=setup_state,
        summary=summary,
        data_completeness_pct=_combine_completeness(
            daily_signal.data_completeness_pct,
            submodules,
        ),
        low_confidence="low_confidence" in risk_flags,
        risk_flags=risk_flags,
        key_support=submodules.multi_timeframe.key_support,
        key_resistance=submodules.multi_timeframe.key_resistance,
        volume_pattern=_map_volume_pattern(submodules.volume_price.volume_pattern),
        entry_trigger=entry_trigger,
        target_price=submodules.patterns.target_price,
        stop_loss_price=submodules.patterns.stop_loss_price,
        risk_reward_ratio=submodules.patterns.risk_reward_ratio,
        subsignals=_build_subsignals(
            daily_signal=daily_signal,
            submodules=submodules,
            structure_signal=structure_signal,
            momentum_signal=momentum_signal,
            volume_signal=volume_signal,
            pattern_signal=pattern_signal,
        ),
    )


def _resolve_setup_state(
    *,
    direction: AnalysisDirection,
    low_confidence: bool,
) -> TechnicalSetupState:
    if low_confidence:
        return TechnicalSetupState.WATCH
    if direction == AnalysisDirection.NEUTRAL:
        return TechnicalSetupState.WATCH
    return TechnicalSetupState.ACTIONABLE


def _build_risk_flags(
    *,
    direction: AnalysisDirection,
    low_confidence: bool,
) -> list[str]:
    flags: list[str] = []
    if low_confidence:
        flags.append("low_confidence")
    if direction == AnalysisDirection.NEUTRAL:
        flags.append("neutral_signal")
    return flags


def _resolve_structure_signal(result: MultiTimeframeResult) -> AnalysisDirection:
    if result.trend_daily == result.trend_weekly == AnalysisDirection.BULLISH.value:
        if result.ma_alignment in {"fully_bullish", "partially_bullish"}:
            return AnalysisDirection.BULLISH
        return AnalysisDirection.NEUTRAL
    if result.trend_daily == result.trend_weekly == AnalysisDirection.BEARISH.value:
        if result.ma_alignment == "fully_bearish":
            return AnalysisDirection.BEARISH
        return AnalysisDirection.NEUTRAL
    return AnalysisDirection.NEUTRAL


def _resolve_momentum_signal(result: MomentumResult) -> AnalysisDirection:
    votes = {"bullish": 0, "bearish": 0}
    strong_bearish = False
    strong_bullish = False

    if result.rsi is not None:
        if result.rsi > 50:
            votes["bullish"] += 1
        elif result.rsi < 50:
            votes["bearish"] += 1
        strong_bearish = result.rsi < 40
        strong_bullish = result.rsi > 60

    if result.macd_signal == "bullish_cross":
        votes["bullish"] += 1
    elif result.macd_signal == "bearish_cross":
        votes["bearish"] += 1

    if result.relative_strength is not None:
        if result.relative_strength > 1.0:
            votes["bullish"] += 1
        elif result.relative_strength < 1.0:
            votes["bearish"] += 1
        strong_bearish = strong_bearish or result.relative_strength < 0.8
        strong_bullish = strong_bullish or result.relative_strength > 1.2

    if votes["bullish"] >= 2 and not strong_bearish:
        return AnalysisDirection.BULLISH
    if votes["bearish"] >= 2 and not strong_bullish:
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL


def _resolve_volume_signal(result: VolumePriceResult) -> AnalysisDirection:
    if result.breakout_confirmed:
        return AnalysisDirection.BULLISH
    if result.breakdown_confirmed:
        return AnalysisDirection.BEARISH
    if result.volume_pattern == VolumePattern.ACCUMULATION.value and result.obv_divergence == "bullish":
        return AnalysisDirection.BULLISH
    if result.volume_pattern == VolumePattern.DISTRIBUTION.value and result.obv_divergence == "bearish":
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL


def _resolve_pattern_signal(result: PatternRecognitionResult) -> AnalysisDirection:
    if result.pattern_quality == "low":
        return AnalysisDirection.NEUTRAL
    if result.pattern_direction == AnalysisDirection.BULLISH.value:
        return AnalysisDirection.BULLISH
    if result.pattern_direction == AnalysisDirection.BEARISH.value:
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL


def _resolve_adx_confidence(adx: float | None) -> float:
    if adx is None:
        return 1.0
    if adx >= 25:
        return 1.0
    if adx >= 20:
        return 0.75
    return 0.5


def _resolve_technical_signal(
    *,
    structure_signal: AnalysisDirection,
    momentum_signal: AnalysisDirection,
    volume_signal: AnalysisDirection,
    pattern_signal: AnalysisDirection,
    adx_confidence: float,
) -> AnalysisDirection:
    score = (
        _signal_value(structure_signal) * 0.35
        + _signal_value(momentum_signal) * adx_confidence * 0.25
        + _signal_value(volume_signal) * 0.20
        + _signal_value(pattern_signal) * 0.20
    )
    if score > 0.30:
        return AnalysisDirection.BULLISH
    if score < -0.30:
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL


def _signal_value(signal: AnalysisDirection) -> int:
    if signal == AnalysisDirection.BULLISH:
        return 1
    if signal == AnalysisDirection.BEARISH:
        return -1
    return 0


def _merge_risk_flags(
    risk_flags: tuple[str, ...],
    *,
    direction: AnalysisDirection,
    low_confidence: bool,
) -> list[str]:
    merged = list(risk_flags)
    merged.extend(_build_risk_flags(direction=direction, low_confidence=low_confidence))
    seen: set[str] = set()
    stable: list[str] = []
    for flag in merged:
        if flag not in seen:
            stable.append(flag)
            seen.add(flag)
    return stable


def _resolve_rich_setup_state(
    *,
    technical_signal: AnalysisDirection,
    submodules: TechnicalSubmoduleBundle,
    risk_flags: list[str],
    structure_signal: AnalysisDirection,
    momentum_signal: AnalysisDirection,
    volume_signal: AnalysisDirection,
    pattern_signal: AnalysisDirection,
) -> TechnicalSetupState:
    directional_signals = {structure_signal, momentum_signal, volume_signal, pattern_signal}
    has_bullish = AnalysisDirection.BULLISH in directional_signals
    has_bearish = AnalysisDirection.BEARISH in directional_signals
    high_risk_count = sum(
        flag.startswith(prefix)
        for flag in risk_flags
        for prefix in ("high volatility:", "deep drawdown:", "iv premium:", "extreme beta:")
    )
    avoid = (
        (technical_signal == AnalysisDirection.NEUTRAL and has_bullish and has_bearish)
        or submodules.risk_metrics.atr_pct > 5
        or abs(submodules.risk_metrics.max_drawdown_63d) > 0.20
        or (submodules.risk_metrics.iv_vs_hv is not None and submodules.risk_metrics.iv_vs_hv > 1.5)
        or any(flag.startswith("severe drawdown:") or flag.startswith("extreme iv premium:") for flag in risk_flags)
        or high_risk_count >= 2
    )
    if avoid:
        return TechnicalSetupState.AVOID

    has_confirmation = (
        submodules.volume_price.breakout_confirmed
        or submodules.volume_price.breakdown_confirmed
        or (
            submodules.patterns.pattern_detected != "none"
            and submodules.patterns.pattern_quality in {"medium", "high"}
            and submodules.patterns.entry_trigger is not None
        )
    )
    if (
        technical_signal != AnalysisDirection.NEUTRAL
        and has_confirmation
        and submodules.patterns.target_price is not None
        and submodules.patterns.stop_loss_price is not None
        and submodules.patterns.risk_reward_ratio is not None
        and submodules.patterns.risk_reward_ratio >= 2.0
    ):
        return TechnicalSetupState.ACTIONABLE
    return TechnicalSetupState.WATCH


def _format_entry_trigger(result: PatternRecognitionResult) -> str | None:
    if result.entry_trigger is None or result.pattern_detected == "none":
        return None
    direction_word = "above" if result.pattern_direction == AnalysisDirection.BULLISH.value else "below"
    return f"Watch for a move {direction_word} {result.entry_trigger:.2f} to confirm {result.pattern_detected}."


def _build_rich_summary(
    *,
    technical_signal: AnalysisDirection,
    trend: AnalysisDirection,
    setup_state: TechnicalSetupState,
    submodules: TechnicalSubmoduleBundle,
    risk_flags: list[str],
    entry_trigger: str | None,
) -> str:
    direction_text = {
        AnalysisDirection.BULLISH: "bullish",
        AnalysisDirection.BEARISH: "bearish",
        AnalysisDirection.NEUTRAL: "neutral",
        AnalysisDirection.DISQUALIFIED: "neutral",
    }[technical_signal]
    trend_text = trend.value
    confirmation_parts: list[str] = []
    if submodules.volume_price.breakout_confirmed:
        confirmation_parts.append("volume confirmed a breakout")
    if submodules.volume_price.breakdown_confirmed:
        confirmation_parts.append("volume confirmed a breakdown")
    if submodules.patterns.pattern_detected != "none":
        confirmation_parts.append(
            f"{submodules.patterns.pattern_detected} pattern quality is {submodules.patterns.pattern_quality}"
        )
    if not confirmation_parts:
        confirmation_parts.append("confirmation remains limited")

    risk_text = "no major risk flags"
    material_flags = [flag for flag in risk_flags if flag not in {"low_confidence", "neutral_signal"}]
    if material_flags:
        risk_text = material_flags[0]

    action_text = {
        TechnicalSetupState.ACTIONABLE: "setup is actionable",
        TechnicalSetupState.WATCH: "setup is on watch",
        TechnicalSetupState.AVOID: "setup should be avoided",
    }[setup_state]

    summary = (
        f"Technical signal is {direction_text} while structure trend is {trend_text}. "
        f"{'; '.join(confirmation_parts)}. "
        f"Volume pattern is {submodules.volume_price.volume_pattern} and momentum reads {submodules.momentum.rsi_signal or 'limited'}. "
        f"Risk context: {risk_text}; {action_text}."
    )
    if entry_trigger is not None and setup_state != TechnicalSetupState.AVOID:
        summary += f" {entry_trigger}"
    return summary


def _combine_completeness(
    daily_signal_pct: float,
    submodules: TechnicalSubmoduleBundle,
) -> float:
    return round(
        fmean(
            [
                daily_signal_pct,
                submodules.multi_timeframe.data_completeness_pct,
                submodules.momentum.data_completeness_pct,
                submodules.volume_price.data_completeness_pct,
                submodules.risk_metrics.data_completeness_pct,
                submodules.patterns.data_completeness_pct,
            ]
        ),
        2,
    )


def _map_volume_pattern(value: str) -> VolumePattern:
    return VolumePattern(value)


def _build_subsignals(
    *,
    daily_signal: TechnicalSignal,
    submodules: TechnicalSubmoduleBundle,
    structure_signal: AnalysisDirection,
    momentum_signal: AnalysisDirection,
    volume_signal: AnalysisDirection,
    pattern_signal: AnalysisDirection,
) -> dict[str, TechnicalSignal]:
    return {
        "daily_bars": daily_signal,
        "multi_timeframe": TechnicalSignal(
            direction=structure_signal,
            summary=(
                f"Daily trend={submodules.multi_timeframe.trend_daily}, "
                f"weekly trend={submodules.multi_timeframe.trend_weekly}, "
                f"MA alignment={submodules.multi_timeframe.ma_alignment}."
            ),
            data_completeness_pct=submodules.multi_timeframe.data_completeness_pct,
            low_confidence=submodules.multi_timeframe.low_confidence,
        ),
        "momentum": TechnicalSignal(
            direction=momentum_signal,
            summary=submodules.momentum.momentum_summary,
            data_completeness_pct=submodules.momentum.data_completeness_pct,
            low_confidence=submodules.momentum.low_confidence,
        ),
        "volume_price": TechnicalSignal(
            direction=volume_signal,
            summary=(
                f"OBV trend={submodules.volume_price.obv_trend}, "
                f"divergence={submodules.volume_price.obv_divergence}, "
                f"volume pattern={submodules.volume_price.volume_pattern}."
            ),
            data_completeness_pct=submodules.volume_price.data_completeness_pct,
            low_confidence=submodules.volume_price.low_confidence,
        ),
        "patterns": TechnicalSignal(
            direction=pattern_signal,
            summary=(
                f"Pattern={submodules.patterns.pattern_detected}, "
                f"quality={submodules.patterns.pattern_quality}."
            ),
            data_completeness_pct=submodules.patterns.data_completeness_pct,
            low_confidence=submodules.patterns.low_confidence,
        ),
        "risk_metrics": TechnicalSignal(
            direction=_risk_signal(submodules.risk_metrics.risk_flags),
            summary=(
                f"ATR={submodules.risk_metrics.atr_pct:.2f}% of price, "
                f"max drawdown={abs(submodules.risk_metrics.max_drawdown_63d) * 100:.1f}%, "
                f"flags={len(submodules.risk_metrics.risk_flags)}."
            ),
            data_completeness_pct=submodules.risk_metrics.data_completeness_pct,
            low_confidence=submodules.risk_metrics.low_confidence,
        ),
    }


def _risk_signal(risk_flags: tuple[str, ...]) -> AnalysisDirection:
    if any(flag.startswith(("severe drawdown:", "extreme iv premium:", "high volatility:")) for flag in risk_flags):
        return AnalysisDirection.BEARISH
    return AnalysisDirection.NEUTRAL

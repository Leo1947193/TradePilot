from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean
from typing import Protocol


class BarLike(Protocol):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


RsiSignal = str
MacdSignal = str
AdxTrendStrength = str


@dataclass(frozen=True)
class MomentumResult:
    rsi: float | None
    rsi_signal: RsiSignal | None
    macd_signal: MacdSignal | None
    adx: float | None
    adx_trend_strength: AdxTrendStrength | None
    benchmark_used: str | None
    relative_strength: float | None
    momentum_summary: str
    data_completeness_pct: float
    low_confidence: bool
    warnings: list[str]


def analyze_momentum(
    daily_bars: list[BarLike],
    benchmark_bars: list[BarLike],
    *,
    benchmark_symbol: str | None = None,
) -> MomentumResult:
    warnings: list[str] = []
    _validate_bars(daily_bars, field_name="daily_bars")
    if benchmark_bars:
        _validate_bars(benchmark_bars, field_name="benchmark_bars")

    closes = [bar.close for bar in daily_bars]
    adx_value = _calculate_adx(daily_bars)
    adx_strength = _classify_adx_strength(adx_value) if adx_value is not None else None
    rsi_value = _calculate_rsi(closes)
    rsi_signal = _classify_rsi_signal(rsi_value, adx_value)
    macd_signal, histogram_state = _calculate_macd_signal(closes)

    if len(daily_bars) < 15:
        warnings.append("daily_bars has fewer than 15 bars; momentum indicators unavailable")
    elif len(daily_bars) < 35:
        warnings.append("daily_bars has fewer than 35 bars; MACD is unavailable")
    elif len(daily_bars) < 63:
        warnings.append("daily_bars has fewer than 63 bars; relative strength is unavailable")
    if adx_value is not None and len(daily_bars) < 150:
        warnings.append("ADX warm-up is below 150 bars; precision is limited")

    benchmark_used: str | None = None
    relative_strength: float | None = None
    rs_trend: str | None = None
    if benchmark_bars and benchmark_symbol:
        benchmark_used = benchmark_symbol
        relative_strength, rs_trend = _calculate_relative_strength(daily_bars, benchmark_bars)
        if relative_strength is None:
            warnings.append("benchmark_bars does not have enough aligned history for relative strength")
    elif benchmark_bars:
        warnings.append("benchmark_symbol is missing; relative strength is unavailable")
    else:
        warnings.append("benchmark_bars is missing; relative strength is unavailable")

    availability = [
        rsi_value is not None,
        macd_signal is not None,
        adx_value is not None,
        relative_strength is not None,
    ]
    data_completeness_pct = round(sum(25.0 for available in availability if available), 1)

    summary = _build_summary(
        rsi=rsi_value,
        rsi_signal=rsi_signal,
        macd_signal=macd_signal,
        histogram_state=histogram_state,
        adx=adx_value,
        adx_strength=adx_strength,
        relative_strength=relative_strength,
        rs_trend=rs_trend,
        benchmark_used=benchmark_used,
        daily_bars=daily_bars,
        warnings=warnings,
    )

    return MomentumResult(
        rsi=_round_or_none(rsi_value, digits=1),
        rsi_signal=rsi_signal,
        macd_signal=macd_signal,
        adx=_round_or_none(adx_value, digits=1),
        adx_trend_strength=adx_strength,
        benchmark_used=benchmark_used,
        relative_strength=_round_or_none(relative_strength, digits=2),
        momentum_summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=bool(warnings),
        warnings=warnings,
    )


def _validate_bars(bars: list[BarLike], *, field_name: str) -> None:
    if not bars:
        raise ValueError(f"{field_name} must not be empty")

    symbol = bars[0].symbol
    last_timestamp = bars[0].timestamp
    _validate_price_bar(bars[0], field_name=field_name)
    for bar in bars[1:]:
        _validate_price_bar(bar, field_name=field_name)
        if bar.symbol != symbol:
            raise ValueError(f"{field_name} must use a single symbol")
        if bar.timestamp <= last_timestamp:
            raise ValueError(f"{field_name} must be sorted in ascending timestamp order")
        last_timestamp = bar.timestamp


def _validate_price_bar(bar: BarLike, *, field_name: str) -> None:
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        raise ValueError(f"{field_name} contains non-positive prices")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError(f"{field_name} contains inconsistent OHLC values")


def _calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None

    changes = [current - previous for previous, current in zip(closes, closes[1:], strict=False)]
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]

    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    for gain, loss in zip(gains[period:], losses[period:], strict=False):
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0

    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def _classify_rsi_signal(rsi: float | None, adx: float | None) -> RsiSignal | None:
    if rsi is None:
        return None

    trending_market = adx is not None and adx >= 25
    if trending_market:
        if rsi >= 80:
            return "overbought"
        if rsi < 40:
            return "oversold"
        return "healthy"

    if rsi >= 70:
        return "overbought"
    if rsi < 30:
        return "oversold"
    return "healthy"


def _calculate_macd_signal(closes: list[float]) -> tuple[MacdSignal | None, str | None]:
    if len(closes) < 35:
        return None, None

    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    offset = len(ema12) - len(ema26)
    macd_line = [fast - slow for fast, slow in zip(ema12[offset:], ema26, strict=False)]
    signal_line = _ema_series(macd_line, 9)
    signal_offset = len(macd_line) - len(signal_line)
    aligned_macd = macd_line[signal_offset:]
    histogram = [macd - signal for macd, signal in zip(aligned_macd, signal_line, strict=False)]

    close = closes[-1]
    if abs(aligned_macd[-1]) < close * 0.001 and abs(histogram[-1]) < close * 0.0005:
        return "flat", _histogram_state(histogram)

    signal = "flat"
    last_index = len(aligned_macd) - 1
    for index in range(1, len(aligned_macd)):
        if aligned_macd[index] > signal_line[index] and aligned_macd[index - 1] <= signal_line[index - 1]:
            if index + 1 <= last_index and histogram[index] > 0 and histogram[index + 1] > 0:
                if last_index - index <= 5:
                    signal = "bullish_cross"
        if aligned_macd[index] < signal_line[index] and aligned_macd[index - 1] >= signal_line[index - 1]:
            if index + 1 <= last_index and histogram[index] < 0 and histogram[index + 1] < 0:
                if last_index - index <= 5:
                    signal = "bearish_cross"

    return signal, _histogram_state(histogram)


def _histogram_state(histogram: list[float]) -> str | None:
    if len(histogram) < 3:
        return None

    trailing = histogram[-3:]
    absolute_values = [abs(value) for value in trailing]
    same_sign = all(value > 0 for value in trailing) or all(value < 0 for value in trailing)
    if same_sign and absolute_values[0] < absolute_values[1] < absolute_values[2]:
        return "expanding"
    if same_sign and absolute_values[0] > absolute_values[1] > absolute_values[2]:
        return "contracting"
    return None


def _calculate_adx(bars: list[BarLike], period: int = 14) -> float | None:
    if len(bars) < (period * 2):
        return None

    true_ranges: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for previous, current in zip(bars, bars[1:], strict=False):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    smoothed_tr = sum(true_ranges[:period])
    smoothed_plus_dm = sum(plus_dm[:period])
    smoothed_minus_dm = sum(minus_dm[:period])
    dx_values: list[float] = []

    for index in range(period, len(true_ranges)):
        if index > period:
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_ranges[index]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm[index]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm[index]

        if smoothed_tr == 0:
            dx_values.append(0.0)
            continue

        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100
        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx_values.append(0.0)
        else:
            dx_values.append((abs(plus_di - minus_di) / di_sum) * 100)

    if len(dx_values) < period:
        return None

    adx = fmean(dx_values[:period])
    for dx in dx_values[period:]:
        adx = ((adx * (period - 1)) + dx) / period
    return adx


def _classify_adx_strength(adx: float | None) -> AdxTrendStrength | None:
    if adx is None:
        return None
    if adx >= 25:
        return "strong"
    if adx >= 20:
        return "moderate"
    return "weak"


def _calculate_relative_strength(
    stock_bars: list[BarLike],
    benchmark_bars: list[BarLike],
) -> tuple[float | None, str | None]:
    benchmark_by_timestamp = {bar.timestamp: bar.close for bar in benchmark_bars}
    aligned_pairs = [
        (stock_bar.timestamp, stock_bar.close, benchmark_by_timestamp[stock_bar.timestamp])
        for stock_bar in stock_bars
        if stock_bar.timestamp in benchmark_by_timestamp
    ]
    if len(aligned_pairs) < 64:
        return None, None

    rs_series: list[float] = []
    for index in range(63, len(aligned_pairs)):
        _, stock_close, bench_close = aligned_pairs[index]
        _, stock_base, bench_base = aligned_pairs[index - 63]
        stock_return = (stock_close - stock_base) / stock_base
        bench_return = (bench_close - bench_base) / bench_base
        rs_series.append((1 + stock_return) / (1 + bench_return))

    if not rs_series:
        return None, None

    current = rs_series[-1]
    if len(rs_series) >= 22:
        past = rs_series[-22]
        if current > past * 1.02:
            trend = "improving"
        elif current < past * 0.98:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return current, trend


def _build_summary(
    *,
    rsi: float | None,
    rsi_signal: RsiSignal | None,
    macd_signal: MacdSignal | None,
    histogram_state: str | None,
    adx: float | None,
    adx_strength: AdxTrendStrength | None,
    relative_strength: float | None,
    rs_trend: str | None,
    benchmark_used: str | None,
    daily_bars: list[BarLike],
    warnings: list[str],
) -> str:
    if len(daily_bars) < 15:
        return "数据不足，无法计算动量指标"

    adx_fragment = "ADX 不可用"
    if adx is not None and adx_strength == "strong":
        adx_fragment = f"趋势明确（ADX {adx:.1f}）"
    elif adx is not None and adx_strength == "moderate":
        adx_fragment = f"趋势温和（ADX {adx:.1f}）"
    elif adx is not None:
        adx_fragment = f"震荡环境（ADX {adx:.1f}），动量信号可靠性降低"

    rsi_fragment = "RSI 不可用"
    if rsi is not None and rsi_signal == "overbought":
        rsi_fragment = f"RSI {rsi:.1f} 超买"
    elif rsi is not None and rsi_signal == "oversold":
        rsi_fragment = f"RSI {rsi:.1f} 超卖"
    elif rsi is not None:
        flavor = "偏强" if rsi > 50 else "偏弱"
        rsi_fragment = f"RSI {rsi:.1f} {flavor}"

    macd_fragment = "MACD 不可用"
    if macd_signal == "bullish_cross":
        macd_fragment = "MACD 看涨交叉"
        if histogram_state == "expanding":
            macd_fragment += "，柱状图扩张"
    elif macd_signal == "bearish_cross":
        macd_fragment = "MACD 看跌交叉"
        if histogram_state == "expanding":
            macd_fragment += "，柱状图扩张"
    elif macd_signal == "flat":
        macd_fragment = "MACD 无明确信号"
        if histogram_state == "contracting":
            macd_fragment = "MACD 平稳，动量收敛"

    rs_fragment = "相对强度不可用"
    if relative_strength is not None and benchmark_used:
        if relative_strength > 1.1 and rs_trend == "improving":
            rs_fragment = f"相对 {benchmark_used} 强于 {benchmark_used}（RS {relative_strength:.2f}，持续走强）"
        elif relative_strength > 1.0 and rs_trend == "improving":
            rs_fragment = f"相对 {benchmark_used} 略强于 {benchmark_used}（RS {relative_strength:.2f}，趋势改善）"
        elif relative_strength > 1.0:
            rs_fragment = f"相对 {benchmark_used} 略强于 {benchmark_used}（RS {relative_strength:.2f}）"
        elif rs_trend == "declining":
            rs_fragment = f"相对 {benchmark_used} 弱于 {benchmark_used}（RS {relative_strength:.2f}，持续走弱）"
        else:
            rs_fragment = f"相对 {benchmark_used} 弱于 {benchmark_used}（RS {relative_strength:.2f}）"
        if relative_strength < 0.8:
            rs_fragment += "，显著落后"

    fragments = [f"{adx_fragment}。", f"{rsi_fragment}，{macd_fragment}。", f"{rs_fragment}。"]
    if rsi in {0.0, 100.0}:
        fragments.append("RSI 达到极端值。")
    if adx is not None and adx > 50:
        fragments.append("趋势极强。")
    if relative_strength is not None and (relative_strength > 2.0 or relative_strength < 0.5):
        fragments.append("相对强度偏离异常，建议核实数据。")
    if any(abs(current.close - previous.close) / previous.close > 0.2 for previous, current in zip(daily_bars, daily_bars[1:], strict=False)):
        fragments.append("近期出现大幅波动。")
    if warnings:
        fragments.append("数据存在降级项。")
    return "".join(fragments)


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        raise ValueError(f"need at least {period} values for EMA")

    multiplier = 2 / (period + 1)
    seed = fmean(values[:period])
    ema_values = [seed]
    for value in values[period:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _round_or_none(value: float | None, *, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)

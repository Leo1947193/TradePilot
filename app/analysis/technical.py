from __future__ import annotations

from dataclasses import dataclass

from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import MarketBar


@dataclass(frozen=True)
class TechnicalSignal:
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


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

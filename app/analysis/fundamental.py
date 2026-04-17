from __future__ import annotations

from dataclasses import dataclass

from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import FinancialSnapshot


@dataclass(frozen=True)
class FundamentalSignal:
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


def analyze_financial_snapshot(snapshot: FinancialSnapshot) -> FundamentalSignal:
    completeness_fields = (
        snapshot.revenue,
        snapshot.net_income,
        snapshot.eps,
        snapshot.gross_margin_pct,
        snapshot.operating_margin_pct,
        snapshot.pe_ratio,
        snapshot.market_cap,
    )
    present_fields = sum(value is not None for value in completeness_fields)
    data_completeness_pct = present_fields / len(completeness_fields) * 100

    positive_signals = 0
    negative_signals = 0

    if snapshot.net_income is not None and snapshot.net_income > 0:
        positive_signals += 1
    elif snapshot.net_income is not None and snapshot.net_income <= 0:
        negative_signals += 1

    if snapshot.eps is not None and snapshot.eps > 0:
        positive_signals += 1
    elif snapshot.eps is not None and snapshot.eps <= 0:
        negative_signals += 1

    if snapshot.gross_margin_pct is not None and snapshot.gross_margin_pct >= 40:
        positive_signals += 1
    elif snapshot.gross_margin_pct is not None and snapshot.gross_margin_pct < 20:
        negative_signals += 1

    if snapshot.operating_margin_pct is not None and snapshot.operating_margin_pct >= 20:
        positive_signals += 1
    elif snapshot.operating_margin_pct is not None and snapshot.operating_margin_pct < 10:
        negative_signals += 1

    if snapshot.pe_ratio is not None and 0 < snapshot.pe_ratio <= 35:
        positive_signals += 1
    elif snapshot.pe_ratio is not None and snapshot.pe_ratio > 50:
        negative_signals += 1

    if positive_signals >= negative_signals + 2:
        direction = AnalysisDirection.BULLISH
        bias_label = "bullish"
    elif negative_signals >= positive_signals + 2:
        direction = AnalysisDirection.BEARISH
        bias_label = "bearish"
    else:
        direction = AnalysisDirection.NEUTRAL
        bias_label = "neutral"

    low_confidence = data_completeness_pct < 60 or direction == AnalysisDirection.NEUTRAL
    metric_bits: list[str] = []
    if snapshot.market_cap is not None:
        metric_bits.append(f"market cap {snapshot.market_cap:.0f}")
    if snapshot.pe_ratio is not None:
        metric_bits.append(f"PE {snapshot.pe_ratio:.2f}")
    if snapshot.eps is not None:
        metric_bits.append(f"EPS {snapshot.eps:.2f}")

    summary = (
        f"Fundamental analysis reviewed {present_fields} of {len(completeness_fields)} core fields "
        f"and found a {bias_label} bias "
        f"(positive signals: {positive_signals}, negative signals: {negative_signals})."
    )
    if metric_bits:
        summary += " Key fields: " + ", ".join(metric_bits) + "."

    return FundamentalSignal(
        direction=direction,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )

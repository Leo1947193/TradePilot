from __future__ import annotations

from app.analysis.fundamental.schemas import (
    FundamentalAggregateResult,
    FundamentalSignal,
    FundamentalSubmoduleBundle,
)
from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import FinancialSnapshot

CORE_FIELD_COUNT = 7
SINGLE_SNAPSHOT_SUBRESULT_KEY = "financial_snapshot"
SINGLE_SNAPSHOT_WEIGHT_SCHEME = "single_snapshot_v1"


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
    key_metrics: list[str] = []
    if snapshot.market_cap is not None:
        key_metrics.append(f"market cap {snapshot.market_cap:.0f}")
    if snapshot.pe_ratio is not None:
        key_metrics.append(f"PE {snapshot.pe_ratio:.2f}")
    if snapshot.eps is not None:
        key_metrics.append(f"EPS {snapshot.eps:.2f}")

    summary = (
        f"Fundamental analysis reviewed {present_fields} of {len(completeness_fields)} core fields "
        f"and found a {bias_label} bias "
        f"(positive signals: {positive_signals}, negative signals: {negative_signals})."
    )
    if key_metrics:
        summary += " Key fields: " + ", ".join(key_metrics) + "."

    return FundamentalSignal(
        direction=direction,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        present_fields=present_fields,
        total_fields=CORE_FIELD_COUNT,
        key_metrics=key_metrics,
    )


def aggregate_fundamental_signals(
    snapshot_signal: FundamentalSignal,
    *,
    submodules: FundamentalSubmoduleBundle | None = None,
) -> FundamentalAggregateResult:
    if submodules is None:
        subresults: dict[str, object] = {SINGLE_SNAPSHOT_SUBRESULT_KEY: snapshot_signal}
        fundamental_bias = snapshot_signal.direction
        key_risks = _build_key_risks(snapshot_signal)
        low_confidence = snapshot_signal.low_confidence
        low_confidence_modules = (
            [SINGLE_SNAPSHOT_SUBRESULT_KEY] if snapshot_signal.low_confidence else []
        )
        summary = snapshot_signal.summary
        weight_scheme_used = SINGLE_SNAPSHOT_WEIGHT_SCHEME
    else:
        subresults = {
            SINGLE_SNAPSHOT_SUBRESULT_KEY: snapshot_signal,
            "financial_health": submodules.financial_health,
            "earnings_momentum": submodules.earnings_momentum,
            "valuation_anchor": submodules.valuation_anchor,
        }
        fundamental_bias = _resolve_fundamental_bias(snapshot_signal, submodules)
        key_risks = _build_integrated_key_risks(snapshot_signal, submodules)
        low_confidence_modules = _resolve_low_confidence_modules(snapshot_signal, submodules)
        low_confidence = bool(low_confidence_modules)
        summary = _build_integrated_summary(snapshot_signal, submodules, fundamental_bias)
        weight_scheme_used = "single_snapshot_plus_submodules_v1"

    return FundamentalAggregateResult(
        fundamental_bias=fundamental_bias,
        composite_score=float(snapshot_signal.positive_signals - snapshot_signal.negative_signals),
        key_risks=key_risks,
        data_completeness_pct=snapshot_signal.data_completeness_pct,
        low_confidence=low_confidence,
        low_confidence_modules=low_confidence_modules,
        weight_scheme_used=weight_scheme_used,
        subresults=subresults,
        summary=summary,
    )


def _build_key_risks(snapshot_signal: FundamentalSignal) -> list[str]:
    risks: list[str] = []
    if snapshot_signal.data_completeness_pct < 60:
        risks.append("limited_fundamental_inputs")
    if snapshot_signal.direction == AnalysisDirection.BEARISH:
        risks.append("negative_snapshot_bias")
    if snapshot_signal.direction == AnalysisDirection.NEUTRAL:
        risks.append("mixed_snapshot_signals")
    return risks


def _resolve_fundamental_bias(
    snapshot_signal: FundamentalSignal,
    submodules: FundamentalSubmoduleBundle,
) -> AnalysisDirection:
    if getattr(submodules.financial_health, "disqualify", False):
        return AnalysisDirection.DISQUALIFIED
    return snapshot_signal.direction


def _build_integrated_key_risks(
    snapshot_signal: FundamentalSignal,
    submodules: FundamentalSubmoduleBundle,
) -> list[str]:
    risks = _build_key_risks(snapshot_signal)

    if getattr(submodules.financial_health, "disqualify", False):
        risks.append("financial_health_disqualify")
    for reason in getattr(submodules.financial_health, "hard_risk_reasons", ()):
        risks.append(str(reason))

    earnings_confidence = getattr(getattr(submodules.earnings_momentum, "confidence", None), "confidence_level", None)
    if earnings_confidence == "Low":
        risks.append("earnings_momentum_low_confidence")

    if getattr(submodules.valuation_anchor, "low_confidence", False):
        risks.append("valuation_anchor_low_confidence")

    deduped: list[str] = []
    for risk in risks:
        if risk not in deduped:
            deduped.append(risk)
    return deduped


def _resolve_low_confidence_modules(
    snapshot_signal: FundamentalSignal,
    submodules: FundamentalSubmoduleBundle,
) -> list[str]:
    modules: list[str] = []
    if snapshot_signal.low_confidence:
        modules.append(SINGLE_SNAPSHOT_SUBRESULT_KEY)
    if getattr(submodules.financial_health, "low_confidence", False):
        modules.append("financial_health")
    if getattr(getattr(submodules.earnings_momentum, "confidence", None), "confidence_level", None) == "Low":
        modules.append("earnings_momentum")
    if getattr(submodules.valuation_anchor, "low_confidence", False):
        modules.append("valuation_anchor")
    return modules


def _build_integrated_summary(
    snapshot_signal: FundamentalSignal,
    submodules: FundamentalSubmoduleBundle,
    fundamental_bias: AnalysisDirection,
) -> str:
    parts = [snapshot_signal.summary]
    if getattr(submodules.financial_health, "disqualify", False):
        parts.append("Financial health triggered a disqualifying hard-risk gate.")
    else:
        parts.append(
            f"Financial health rating is {getattr(submodules.financial_health, 'overall_rating', 'Low')}."
        )

    earnings_label = getattr(getattr(submodules.earnings_momentum, "metrics", None), "earnings_momentum", None)
    if earnings_label is not None:
        parts.append(f"Earnings momentum is {earnings_label.lower()}.")

    valuation_score = getattr(submodules.valuation_anchor, "valuation_score", None)
    if valuation_score is not None:
        parts.append(f"Valuation anchor score is {valuation_score}.")

    if fundamental_bias == AnalysisDirection.DISQUALIFIED:
        parts.append("Overall fundamental bias is disqualified.")

    return " ".join(parts)

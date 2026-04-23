from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

ConfidenceLevel = Literal["High", "Medium", "Low"]
GuidanceTrend = Literal["Raised", "Maintained", "Lowered", "NoGuidance"] | None
CurrentQuarterBar = Literal["High", "Normal", "Low"]
MomentumLabel = Literal["Accelerating", "Stable", "Decelerating"]


@dataclass(frozen=True)
class EarningsQuarter:
    report_date: date
    eps_actual: float | None = None
    eps_consensus_pre_report: float | None = None
    revenue_actual: float | None = None
    revenue_consensus_pre_report: float | None = None
    source: str = "standardized_financial_snapshot"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class RevisionSnapshot:
    as_of_date: date
    eps_up_30d: int | None = None
    eps_down_30d: int | None = None
    eps_up_60d: int | None = None
    eps_down_60d: int | None = None
    revenue_up_30d: int | None = None
    revenue_down_30d: int | None = None
    source: str = "standardized_revision_summary"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class CurrentQuarterConsensus:
    as_of_date: date
    eps_consensus_now: float | None = None
    eps_consensus_30d_ago: float | None = None
    source: str = "standardized_current_quarter_consensus"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class GuidanceRecord:
    as_of_date: date
    explicit_no_guidance: bool = False
    eps_low: float | None = None
    eps_high: float | None = None
    revenue_low: float | None = None
    revenue_high: float | None = None
    source: str = "standardized_guidance_history"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class EarningsMomentumInput:
    analysis_timestamp: datetime
    quarterly_results: tuple[EarningsQuarter, ...]
    revision_summary: RevisionSnapshot | None = None
    current_quarter_consensus: CurrentQuarterConsensus | None = None
    guidance_history: tuple[GuidanceRecord, ...] = ()
    ticker: str = "UNKNOWN"
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class EarningsMomentumMetrics:
    eps_beat_streak_quarters: int | None
    avg_eps_surprise_pct_4q: float | None
    avg_revenue_surprise_pct_4q: float | None
    eps_revision_balance_30d: float | None
    eps_revision_balance_60d: float | None
    revenue_revision_balance_30d: float | None
    guidance_trend: GuidanceTrend
    current_quarter_bar: CurrentQuarterBar
    earnings_momentum: MomentumLabel
    earnings_score: int


@dataclass(frozen=True)
class EarningsMomentumSubscores:
    beat_quality_score: int | None
    revision_signal_score: int | None
    revenue_confirmation: int | None
    guidance_score: int | None


@dataclass(frozen=True)
class EarningsMomentumConfidence:
    confidence_score: float
    confidence_level: ConfidenceLevel
    critical_missing_fields: tuple[str, ...]
    stale_fields: tuple[str, ...]


@dataclass(frozen=True)
class EarningsMomentumFlags:
    guidance_data_missing: bool
    used_degraded_quarter_set: bool
    used_normalized_scoring: bool


@dataclass(frozen=True)
class SourceTraceItem:
    dataset: Literal[
        "quarterly_results",
        "revision_summary",
        "current_quarter_consensus",
        "guidance_history",
    ]
    source: str
    fetched_at: str | None
    staleness_days: int | None
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class EarningsMomentumResult:
    schema_version: str
    ticker: str
    analysis_timestamp: str
    module: str
    staleness_days: int | None
    missing_fields: tuple[str, ...]
    metrics: EarningsMomentumMetrics
    subscores: EarningsMomentumSubscores
    confidence: EarningsMomentumConfidence
    flags: EarningsMomentumFlags
    source_trace: tuple[SourceTraceItem, ...]


def analyze_earnings_momentum(dataset: EarningsMomentumInput) -> EarningsMomentumResult:
    analysis_date = dataset.analysis_timestamp.date()
    missing_fields = set(dataset.missing_fields)
    stale_fields: list[str] = []

    quarters = tuple(sorted(dataset.quarterly_results, key=lambda item: item.report_date, reverse=True))
    latest_report_date = quarters[0].report_date if quarters else None
    latest_report_staleness = (
        (analysis_date - latest_report_date).days if latest_report_date is not None else None
    )

    eps_surprises = _surprises(quarters[:4], "eps_actual", "eps_consensus_pre_report")
    revenue_surprises = _surprises(quarters[:4], "revenue_actual", "revenue_consensus_pre_report")
    valid_eps_quarters = len(eps_surprises)
    valid_revenue_quarters = len(revenue_surprises)
    used_degraded_quarter_set = valid_eps_quarters in (2, 3) or valid_revenue_quarters in (2, 3)

    if valid_eps_quarters < 4:
        missing_fields.add("eps_surprise_core")
    if valid_revenue_quarters < 4:
        missing_fields.add("revenue_surprise_core")

    avg_eps_surprise = _average(eps_surprises) if valid_eps_quarters >= 2 else None
    avg_revenue_surprise = _average(revenue_surprises) if valid_revenue_quarters >= 2 else None
    beat_streak = _beat_streak(quarters[:4])

    revision_30_is_stale = False
    revision_60_is_stale = False
    revenue_revision_is_stale = False
    eps_consensus_stale = False

    revision_30 = None
    revision_60 = None
    revenue_revision = None
    if dataset.revision_summary is None:
        missing_fields.update({"eps_revision_core", "revenue_revision_core"})
    else:
        revision_age = (analysis_date - dataset.revision_summary.as_of_date).days
        if revision_age > 14:
            stale_fields.extend(
                ["eps_revision_balance_30d", "eps_revision_balance_60d", "revenue_revision_balance_30d"]
            )
            revision_30_is_stale = True
            revision_60_is_stale = True
            revenue_revision_is_stale = True
        else:
            revision_30 = _revision_balance(
                dataset.revision_summary.eps_up_30d,
                dataset.revision_summary.eps_down_30d,
            )
            revision_60 = _revision_balance(
                dataset.revision_summary.eps_up_60d,
                dataset.revision_summary.eps_down_60d,
            )
            revenue_revision = _revision_balance(
                dataset.revision_summary.revenue_up_30d,
                dataset.revision_summary.revenue_down_30d,
            )
            if revision_30 is None or dataset.revision_summary.eps_up_30d is None or dataset.revision_summary.eps_down_30d is None:
                missing_fields.add("eps_revision_core")
            if revision_60 is None or dataset.revision_summary.eps_up_60d is None or dataset.revision_summary.eps_down_60d is None:
                missing_fields.add("eps_revision_core")
            if (
                revenue_revision is None
                or dataset.revision_summary.revenue_up_30d is None
                or dataset.revision_summary.revenue_down_30d is None
            ):
                missing_fields.add("revenue_revision_core")

    eps_consensus_change = None
    if dataset.current_quarter_consensus is None:
        missing_fields.add("current_quarter_consensus_core")
    else:
        consensus_age = (analysis_date - dataset.current_quarter_consensus.as_of_date).days
        if consensus_age > 14:
            stale_fields.append("current_quarter_consensus_core")
            eps_consensus_stale = True
        else:
            eps_consensus_change = _consensus_change_pct(
                dataset.current_quarter_consensus.eps_consensus_now,
                dataset.current_quarter_consensus.eps_consensus_30d_ago,
            )
            if eps_consensus_change is None:
                missing_fields.add("current_quarter_consensus_core")

    guidance_trend, guidance_data_missing = _guidance_trend(
        dataset.guidance_history,
        analysis_date,
        latest_report_staleness,
        missing_fields,
        stale_fields,
    )

    effective_revision_30 = None if revision_30_is_stale else revision_30
    effective_revision_60 = None if revision_60_is_stale else revision_60
    effective_revenue_revision = None if revenue_revision_is_stale else revenue_revision
    effective_consensus_change = None if eps_consensus_stale else eps_consensus_change

    current_quarter_bar = _current_quarter_bar(
        eps_consensus_change_pct_30d=effective_consensus_change,
        eps_revision_balance_30d=effective_revision_30,
        revenue_revision_balance_30d=effective_revenue_revision,
    )

    beat_quality_score = _beat_quality_score(beat_streak, avg_eps_surprise)
    revision_signal_score = _revision_signal_score(effective_revision_30, effective_revision_60)
    revenue_confirmation = _revenue_confirmation_score(avg_revenue_surprise, effective_revenue_revision)
    guidance_score = None
    if guidance_trend is not None:
        guidance_score = {"Raised": 20, "Maintained": 12, "NoGuidance": 6, "Lowered": 0}[guidance_trend]

    stale_report = latest_report_staleness is not None and latest_report_staleness > 140
    can_accelerate = (
        not stale_report
        and effective_revision_30 is not None
        and not guidance_data_missing
    )
    earnings_momentum = _earnings_momentum(
        avg_eps_surprise_pct_4q=avg_eps_surprise,
        avg_revenue_surprise_pct_4q=avg_revenue_surprise,
        eps_revision_balance_30d=effective_revision_30,
        eps_revision_balance_60d=effective_revision_60,
        eps_beat_streak_quarters=beat_streak,
        guidance_trend=guidance_trend,
        can_accelerate=can_accelerate,
    )

    subscore_values = {
        "beat_quality_score": beat_quality_score,
        "revision_signal_score": revision_signal_score,
        "revenue_confirmation": revenue_confirmation,
        "guidance_score": guidance_score,
    }
    available_score_sum = sum(score for score in subscore_values.values() if score is not None)
    score_caps = {
        "beat_quality_score": 30,
        "revision_signal_score": 35,
        "revenue_confirmation": 15,
        "guidance_score": 20,
    }
    available_score_cap = sum(
        score_caps[name] for name, score in subscore_values.items() if score is not None
    )
    used_normalized_scoring = any(score is None for score in subscore_values.values())

    if used_normalized_scoring:
        missing_penalty = 0
        if beat_quality_score is None:
            missing_penalty += 15
        if revision_signal_score is None:
            missing_penalty += 15
        if revenue_confirmation is None:
            missing_penalty += 5
        if guidance_score is None:
            missing_penalty += 5
        if current_quarter_bar == "Normal" and _bar_signal_count(
            effective_consensus_change, effective_revision_30, effective_revenue_revision
        ) < 2:
            missing_penalty += 5
        if available_score_cap < 60:
            earnings_score = 50
            earnings_momentum = "Stable"
        else:
            normalized = (available_score_sum / available_score_cap) * 100
            earnings_score = max(0, min(100, round(normalized - missing_penalty)))
    else:
        earnings_score = round(available_score_sum)

    if stale_report:
        earnings_score = min(earnings_score, 60)
        if earnings_momentum == "Accelerating":
            earnings_momentum = "Stable"

    confidence = _confidence(
        latest_report_staleness=latest_report_staleness,
        valid_eps_quarters=valid_eps_quarters,
        valid_revenue_quarters=valid_revenue_quarters,
        revision_30_missing=effective_revision_30 is None,
        revision_60_missing=effective_revision_60 is None,
        revenue_revision_missing=effective_revenue_revision is None,
        consensus_missing=effective_consensus_change is None,
        guidance_data_missing=guidance_data_missing,
        stale_fields=tuple(dict.fromkeys(stale_fields)),
        critical_missing_fields=tuple(sorted(missing_fields)),
        forced_low=available_score_cap < 60,
    )
    if available_score_cap < 60:
        earnings_momentum = "Stable"

    source_trace = _source_trace(dataset, analysis_date)

    return EarningsMomentumResult(
        schema_version="1.0",
        ticker=dataset.ticker,
        analysis_timestamp=dataset.analysis_timestamp.isoformat(),
        module="EarningsMomentumAnalyzerV1",
        staleness_days=latest_report_staleness,
        missing_fields=tuple(sorted(missing_fields)),
        metrics=EarningsMomentumMetrics(
            eps_beat_streak_quarters=beat_streak,
            avg_eps_surprise_pct_4q=_round2(avg_eps_surprise),
            avg_revenue_surprise_pct_4q=_round2(avg_revenue_surprise),
            eps_revision_balance_30d=_round2(effective_revision_30),
            eps_revision_balance_60d=_round2(effective_revision_60),
            revenue_revision_balance_30d=_round2(effective_revenue_revision),
            guidance_trend=guidance_trend,
            current_quarter_bar=current_quarter_bar,
            earnings_momentum=earnings_momentum,
            earnings_score=earnings_score,
        ),
        subscores=EarningsMomentumSubscores(
            beat_quality_score=beat_quality_score,
            revision_signal_score=revision_signal_score,
            revenue_confirmation=revenue_confirmation,
            guidance_score=guidance_score,
        ),
        confidence=confidence,
        flags=EarningsMomentumFlags(
            guidance_data_missing=guidance_data_missing,
            used_degraded_quarter_set=used_degraded_quarter_set,
            used_normalized_scoring=used_normalized_scoring,
        ),
        source_trace=source_trace,
    )


def _round2(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _surprises(
    quarters: tuple[EarningsQuarter, ...],
    actual_field: str,
    consensus_field: str,
) -> list[float]:
    surprises: list[float] = []
    for quarter in quarters:
        actual = getattr(quarter, actual_field)
        consensus = getattr(quarter, consensus_field)
        if actual is None or consensus is None or consensus == 0:
            continue
        surprises.append(((actual - consensus) / abs(consensus)) * 100)
    return surprises


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _beat_streak(quarters: tuple[EarningsQuarter, ...]) -> int | None:
    streak = 0
    valid_seen = 0
    for quarter in quarters:
        actual = quarter.eps_actual
        consensus = quarter.eps_consensus_pre_report
        if actual is None or consensus is None or consensus == 0:
            continue
        valid_seen += 1
        surprise = ((actual - consensus) / abs(consensus)) * 100
        if surprise > 0:
            streak += 1
        else:
            break
    return streak if valid_seen else None


def _revision_balance(up: int | None, down: int | None) -> float | None:
    if up is None or down is None:
        return None
    total = up + down
    return (up - down) / max(total, 1)


def _consensus_change_pct(now: float | None, ago_30d: float | None) -> float | None:
    if now is None or ago_30d is None or ago_30d == 0:
        return None
    return ((now - ago_30d) / abs(ago_30d)) * 100


def _guidance_midpoint(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return (low + high) / 2


def _guidance_trend(
    guidance_history: tuple[GuidanceRecord, ...],
    analysis_date: date,
    latest_report_staleness: int | None,
    missing_fields: set[str],
    stale_fields: list[str],
) -> tuple[GuidanceTrend, bool]:
    if not guidance_history:
        missing_fields.add("guidance_core")
        return None, True
    records = tuple(sorted(guidance_history, key=lambda item: item.as_of_date, reverse=True))
    latest = records[0]
    if latest_report_staleness is not None and latest_report_staleness > 140:
        stale_fields.append("guidance_core")
    if latest.explicit_no_guidance:
        return "NoGuidance", False
    if len(records) < 2:
        missing_fields.add("guidance_core")
        return None, True
    previous = records[1]
    comparisons: list[float] = []
    for latest_pair, previous_pair in (
        ((_guidance_midpoint(latest.eps_low, latest.eps_high)), (_guidance_midpoint(previous.eps_low, previous.eps_high))),
        ((_guidance_midpoint(latest.revenue_low, latest.revenue_high)), (_guidance_midpoint(previous.revenue_low, previous.revenue_high))),
    ):
        latest_mid, previous_mid = latest_pair, previous_pair
        if latest_mid is None or previous_mid is None or previous_mid == 0:
            continue
        comparisons.append(((latest_mid - previous_mid) / abs(previous_mid)) * 100)
    if any(change <= -2.0 for change in comparisons):
        return "Lowered", False
    if any(change >= 2.0 for change in comparisons):
        return "Raised", False
    if comparisons and all(-2.0 < change < 2.0 for change in comparisons):
        return "Maintained", False
    if latest.explicit_no_guidance:
        return "NoGuidance", False
    missing_fields.add("guidance_core")
    return None, True


def _bar_signal_count(
    eps_consensus_change_pct_30d: float | None,
    eps_revision_balance_30d: float | None,
    revenue_revision_balance_30d: float | None,
) -> int:
    return sum(
        value is not None
        for value in (eps_consensus_change_pct_30d, eps_revision_balance_30d, revenue_revision_balance_30d)
    )


def _current_quarter_bar(
    *,
    eps_consensus_change_pct_30d: float | None,
    eps_revision_balance_30d: float | None,
    revenue_revision_balance_30d: float | None,
) -> CurrentQuarterBar:
    high_votes = 0
    low_votes = 0
    signal_count = _bar_signal_count(
        eps_consensus_change_pct_30d,
        eps_revision_balance_30d,
        revenue_revision_balance_30d,
    )
    if signal_count < 2:
        return "Normal"
    if eps_consensus_change_pct_30d is not None:
        if eps_consensus_change_pct_30d >= 5.0:
            high_votes += 1
        elif eps_consensus_change_pct_30d <= -5.0:
            low_votes += 1
    if eps_revision_balance_30d is not None:
        if eps_revision_balance_30d >= 0.50:
            high_votes += 1
        elif eps_revision_balance_30d <= -0.50:
            low_votes += 1
    if revenue_revision_balance_30d is not None:
        if revenue_revision_balance_30d >= 0.25:
            high_votes += 1
        elif revenue_revision_balance_30d <= -0.25:
            low_votes += 1
    if high_votes >= 2:
        return "High"
    if low_votes >= 2:
        return "Low"
    return "Normal"


def _earnings_momentum(
    *,
    avg_eps_surprise_pct_4q: float | None,
    avg_revenue_surprise_pct_4q: float | None,
    eps_revision_balance_30d: float | None,
    eps_revision_balance_60d: float | None,
    eps_beat_streak_quarters: int | None,
    guidance_trend: GuidanceTrend,
    can_accelerate: bool,
) -> MomentumLabel:
    if guidance_trend == "Lowered":
        return "Decelerating"
    if eps_revision_balance_30d is not None and eps_revision_balance_30d <= -0.25:
        return "Decelerating"
    if (
        avg_eps_surprise_pct_4q is not None
        and avg_revenue_surprise_pct_4q is not None
        and avg_eps_surprise_pct_4q < 0
        and avg_revenue_surprise_pct_4q < 0
    ):
        return "Decelerating"
    if not can_accelerate:
        return "Stable"
    if (
        avg_eps_surprise_pct_4q is not None
        and avg_eps_surprise_pct_4q >= 2.0
        and eps_revision_balance_30d is not None
        and eps_revision_balance_30d >= 0.25
        and guidance_trend != "Lowered"
        and (
            (eps_beat_streak_quarters is not None and eps_beat_streak_quarters >= 2)
            or (
                eps_revision_balance_60d is not None
                and eps_revision_balance_30d > eps_revision_balance_60d
            )
        )
    ):
        return "Accelerating"
    return "Stable"


def _beat_quality_score(beat_streak: int | None, avg_eps_surprise: float | None) -> int | None:
    if beat_streak is None or avg_eps_surprise is None:
        return None
    streak_score = 0
    if beat_streak >= 4:
        streak_score = 15
    elif beat_streak == 3:
        streak_score = 12
    elif beat_streak == 2:
        streak_score = 8
    elif beat_streak == 1:
        streak_score = 4

    if avg_eps_surprise >= 10.0:
        surprise_score = 15
    elif avg_eps_surprise >= 5.0:
        surprise_score = 12
    elif avg_eps_surprise >= 2.0:
        surprise_score = 9
    elif avg_eps_surprise >= 0.0:
        surprise_score = 6
    elif avg_eps_surprise >= -2.0:
        surprise_score = 3
    else:
        surprise_score = 0
    return streak_score + surprise_score


def _revision_signal_score(
    eps_revision_balance_30d: float | None,
    eps_revision_balance_60d: float | None,
) -> int | None:
    if eps_revision_balance_30d is None and eps_revision_balance_60d is None:
        return None
    score = 0
    if eps_revision_balance_30d is not None:
        score += _band_score(
            eps_revision_balance_30d,
            ((0.50, 20), (0.25, 16), (0.10, 12), (-0.10, 8), (-0.25, 4)),
            0,
        )
    if eps_revision_balance_60d is not None:
        score += _band_score(
            eps_revision_balance_60d,
            ((0.50, 10), (0.25, 8), (0.10, 6), (-0.10, 4), (-0.25, 2)),
            0,
        )
    if eps_revision_balance_30d is not None and eps_revision_balance_60d is not None:
        if eps_revision_balance_30d >= 0.25 and eps_revision_balance_60d >= 0.10:
            score += 5
        elif eps_revision_balance_30d > eps_revision_balance_60d and eps_revision_balance_30d > 0:
            score += 3
        elif abs(eps_revision_balance_30d - eps_revision_balance_60d) < 0.10:
            score += 2
    return score


def _revenue_confirmation_score(
    avg_revenue_surprise_pct_4q: float | None,
    revenue_revision_balance_30d: float | None,
) -> int | None:
    if avg_revenue_surprise_pct_4q is None and revenue_revision_balance_30d is None:
        return None
    score = 0
    if avg_revenue_surprise_pct_4q is not None:
        if avg_revenue_surprise_pct_4q >= 4.0:
            score += 10
        elif avg_revenue_surprise_pct_4q >= 1.0:
            score += 7
        elif avg_revenue_surprise_pct_4q >= -1.0:
            score += 5
        elif avg_revenue_surprise_pct_4q >= -4.0:
            score += 2
    if revenue_revision_balance_30d is not None:
        if revenue_revision_balance_30d >= 0.25:
            score += 5
        elif revenue_revision_balance_30d >= 0.0:
            score += 3
        elif revenue_revision_balance_30d >= -0.25:
            score += 1
    return score


def _band_score(
    value: float,
    bands: tuple[tuple[float, int], ...],
    default: int,
) -> int:
    for threshold, score in bands:
        if value >= threshold:
            return score
    return default


def _confidence(
    *,
    latest_report_staleness: int | None,
    valid_eps_quarters: int,
    valid_revenue_quarters: int,
    revision_30_missing: bool,
    revision_60_missing: bool,
    revenue_revision_missing: bool,
    consensus_missing: bool,
    guidance_data_missing: bool,
    stale_fields: tuple[str, ...],
    critical_missing_fields: tuple[str, ...],
    forced_low: bool,
) -> EarningsMomentumConfidence:
    deduction = 0.0
    if latest_report_staleness is not None:
        if 101 <= latest_report_staleness <= 140:
            deduction += 0.10
        elif latest_report_staleness > 140:
            deduction += 0.20
    if valid_eps_quarters < 4:
        deduction += (4 - valid_eps_quarters) * 0.10
    if valid_revenue_quarters < 4:
        deduction += (4 - valid_revenue_quarters) * 0.05
    if revision_30_missing:
        deduction += 0.15
    if revision_60_missing:
        deduction += 0.10
    if revenue_revision_missing:
        deduction += 0.10
    if consensus_missing:
        deduction += 0.05
    if guidance_data_missing:
        deduction += 0.10
    confidence_score = max(0.20, min(1.00, 1.00 - deduction))
    if forced_low:
        confidence_level: ConfidenceLevel = "Low"
    elif confidence_score >= 0.85:
        confidence_level = "High"
    elif confidence_score >= 0.65:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"
    return EarningsMomentumConfidence(
        confidence_score=round(confidence_score, 2),
        confidence_level=confidence_level,
        critical_missing_fields=critical_missing_fields,
        stale_fields=stale_fields,
    )


def _source_trace(
    dataset: EarningsMomentumInput,
    analysis_date: date,
) -> tuple[SourceTraceItem, ...]:
    items: list[SourceTraceItem] = []
    if dataset.quarterly_results:
        latest_quarter = max(dataset.quarterly_results, key=lambda item: item.report_date)
        items.append(
            SourceTraceItem(
                dataset="quarterly_results",
                source=latest_quarter.source,
                fetched_at=latest_quarter.fetched_at.isoformat() if latest_quarter.fetched_at else None,
                staleness_days=(analysis_date - latest_quarter.report_date).days,
                missing_fields=(),
            )
        )
    if dataset.revision_summary is not None:
        items.append(
            SourceTraceItem(
                dataset="revision_summary",
                source=dataset.revision_summary.source,
                fetched_at=dataset.revision_summary.fetched_at.isoformat()
                if dataset.revision_summary.fetched_at
                else None,
                staleness_days=(analysis_date - dataset.revision_summary.as_of_date).days,
                missing_fields=(),
            )
        )
    if dataset.current_quarter_consensus is not None:
        items.append(
            SourceTraceItem(
                dataset="current_quarter_consensus",
                source=dataset.current_quarter_consensus.source,
                fetched_at=dataset.current_quarter_consensus.fetched_at.isoformat()
                if dataset.current_quarter_consensus.fetched_at
                else None,
                staleness_days=(analysis_date - dataset.current_quarter_consensus.as_of_date).days,
                missing_fields=(),
            )
        )
    if dataset.guidance_history:
        latest_guidance = max(dataset.guidance_history, key=lambda item: item.as_of_date)
        items.append(
            SourceTraceItem(
                dataset="guidance_history",
                source=latest_guidance.source,
                fetched_at=latest_guidance.fetched_at.isoformat() if latest_guidance.fetched_at else None,
                staleness_days=(analysis_date - latest_guidance.as_of_date).days,
                missing_fields=(),
            )
        )
    return tuple(items)

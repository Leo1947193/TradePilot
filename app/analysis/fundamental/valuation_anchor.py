from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import ConfigDict

from app.schemas.modules import ModuleSchema
from app.services.providers.dtos import FinancialSnapshot

MODULE_NAME = "valuation_anchor"
PRIMARY_METRIC_PROXY = "ForwardPE"
SNAPSHOT_PRIMARY_SELECTION_REASON = "SnapshotPERatioProxy"
ALL_METRICS_UNAVAILABLE = "AllMetricsUnavailable"
SNAPSHOT_LIMITATION_WARNING = (
    "FinancialSnapshot fallback only: historical valuation, peers, and forward growth inputs are unavailable."
)
SNAPSHOT_PROXY_WARNING = (
    "Using FinancialSnapshot.pe_ratio as a proxy earnings multiple until valuation_snapshot is implemented."
)
SNAPSHOT_NO_METRIC_WARNING = (
    "FinancialSnapshot fallback could not find a positive comparable valuation multiple."
)


class PegFlag(StrEnum):
    VALID = "Valid"
    NOT_APPLICABLE_PRIMARY_METRIC = "NotApplicablePrimaryMetric"
    MISSING_GROWTH = "MissingGrowth"
    GROWTH_TOO_LOW = "GrowthTooLow"
    NEGATIVE_GROWTH = "NegativeGrowth"
    NEGATIVE_OR_ZERO_MULTIPLE = "NegativeOrZeroMultiple"


class SpaceRating(StrEnum):
    UNDERVALUED = "Undervalued"
    FAIR = "Fair"
    ELEVATED = "Elevated"
    COMPRESSED = "Compressed"


class ConfidenceLevel(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class PeerGroupScope(StrEnum):
    INDUSTRY = "Industry"
    SECTOR = "Sector"
    UNAVAILABLE = "Unavailable"


class ValuationAnchorResult(ModuleSchema):
    model_config = ConfigDict(extra="forbid")

    module: str = MODULE_NAME
    as_of_date: date
    primary_metric_used: str | None
    primary_metric_value: float | None
    primary_metric_selection_reason: str | None
    primary_metric_fallback_reason: str | None
    historical_window_months_used: int
    historical_valid_sample_count: int
    historical_percentile: float | None
    peer_group_scope: PeerGroupScope
    peer_count_used: int
    peer_median_value: float | None
    peer_relative_ratio: float | None
    peg_ratio: float | None
    peg_flag: PegFlag
    space_rating: SpaceRating
    valuation_score: int
    confidence: ConfidenceLevel
    staleness_days: int
    missing_fields: list[str]
    low_confidence: bool
    warnings: list[str]


def analyze_valuation_anchor_from_snapshot(
    snapshot: FinancialSnapshot,
    *,
    analysis_date: date | None = None,
) -> ValuationAnchorResult:
    effective_analysis_date = analysis_date or snapshot.as_of_date
    staleness_days = max((effective_analysis_date - snapshot.as_of_date).days, 0)

    warnings = [SNAPSHOT_LIMITATION_WARNING]
    missing_fields = [
        "valuation_history",
        "peer_multiples",
        "forward_eps_growth_pct_next_12m",
    ]

    current_multiple = _positive_multiple(snapshot.pe_ratio)
    if current_multiple is None:
        missing_fields.append("pe_ratio")
        warnings.append(SNAPSHOT_NO_METRIC_WARNING)
        return ValuationAnchorResult(
            as_of_date=snapshot.as_of_date,
            primary_metric_used=None,
            primary_metric_value=None,
            primary_metric_selection_reason=None,
            primary_metric_fallback_reason=ALL_METRICS_UNAVAILABLE,
            historical_window_months_used=0,
            historical_valid_sample_count=0,
            historical_percentile=None,
            peer_group_scope=PeerGroupScope.UNAVAILABLE,
            peer_count_used=0,
            peer_median_value=None,
            peer_relative_ratio=None,
            peg_ratio=None,
            peg_flag=PegFlag.NOT_APPLICABLE_PRIMARY_METRIC,
            space_rating=SpaceRating.FAIR,
            valuation_score=36,
            confidence=ConfidenceLevel.LOW,
            staleness_days=staleness_days,
            missing_fields=missing_fields,
            low_confidence=True,
            warnings=warnings,
        )

    warnings.append(SNAPSHOT_PROXY_WARNING)
    return ValuationAnchorResult(
        as_of_date=snapshot.as_of_date,
        primary_metric_used=PRIMARY_METRIC_PROXY,
        primary_metric_value=round(current_multiple, 2),
        primary_metric_selection_reason=SNAPSHOT_PRIMARY_SELECTION_REASON,
        primary_metric_fallback_reason=None,
        historical_window_months_used=0,
        historical_valid_sample_count=0,
        historical_percentile=None,
        peer_group_scope=PeerGroupScope.UNAVAILABLE,
        peer_count_used=0,
        peer_median_value=None,
        peer_relative_ratio=None,
        peg_ratio=None,
        peg_flag=PegFlag.MISSING_GROWTH,
        space_rating=SpaceRating.FAIR,
        valuation_score=_score_snapshot_fallback(staleness_days=staleness_days),
        confidence=ConfidenceLevel.LOW,
        staleness_days=staleness_days,
        missing_fields=missing_fields,
        low_confidence=True,
        warnings=warnings,
    )


def _positive_multiple(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return value


def _score_snapshot_fallback(*, staleness_days: int) -> int:
    history_score = 18
    peer_score = 18
    peg_score = 8
    data_quality_score = 0 if staleness_days > 30 else 4
    return history_score + peer_score + peg_score + data_quality_score


ValuationAnchorResult.model_rebuild()

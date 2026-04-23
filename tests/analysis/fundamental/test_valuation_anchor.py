from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.providers.dtos import FinancialSnapshot, ProviderSourceRef


def _load_module():
    module_path = REPO_ROOT / "app/analysis/fundamental/valuation_anchor.py"
    spec = importlib.util.spec_from_file_location("valuation_anchor_worker3", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


valuation_anchor = _load_module()


def make_snapshot(*, pe_ratio: float | None, as_of_date: date = date(2026, 4, 10)) -> FinancialSnapshot:
    return FinancialSnapshot(
        symbol="AAPL",
        as_of_date=as_of_date,
        pe_ratio=pe_ratio,
        source=ProviderSourceRef(
            name="yfinance",
            url="https://finance.yahoo.com/quote/AAPL",
            fetched_at=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
        ),
    )


def test_snapshot_fallback_uses_pe_ratio_as_proxy_and_marks_limitations() -> None:
    result = valuation_anchor.analyze_valuation_anchor_from_snapshot(
        make_snapshot(pe_ratio=22.678),
        analysis_date=date(2026, 4, 22),
    )

    assert result.module == "valuation_anchor"
    assert result.primary_metric_used == "ForwardPE"
    assert result.primary_metric_value == 22.68
    assert result.primary_metric_selection_reason == "SnapshotPERatioProxy"
    assert result.primary_metric_fallback_reason is None
    assert result.historical_percentile is None
    assert result.peer_relative_ratio is None
    assert result.peg_ratio is None
    assert result.peg_flag == valuation_anchor.PegFlag.MISSING_GROWTH
    assert result.space_rating == valuation_anchor.SpaceRating.FAIR
    assert result.valuation_score == 48
    assert result.confidence == valuation_anchor.ConfidenceLevel.LOW
    assert result.staleness_days == 12
    assert result.low_confidence is True
    assert result.missing_fields == [
        "valuation_history",
        "peer_multiples",
        "forward_eps_growth_pct_next_12m",
    ]
    assert result.warnings == [
        valuation_anchor.SNAPSHOT_LIMITATION_WARNING,
        valuation_anchor.SNAPSHOT_PROXY_WARNING,
    ]


def test_snapshot_fallback_zero_or_negative_staleness_is_clamped() -> None:
    result = valuation_anchor.analyze_valuation_anchor_from_snapshot(
        make_snapshot(pe_ratio=15.0, as_of_date=date(2026, 4, 22)),
        analysis_date=date(2026, 4, 10),
    )

    assert result.staleness_days == 0
    assert result.valuation_score == 48


def test_snapshot_fallback_drops_data_quality_after_30_days() -> None:
    result = valuation_anchor.analyze_valuation_anchor_from_snapshot(
        make_snapshot(pe_ratio=18.0, as_of_date=date(2026, 3, 1)),
        analysis_date=date(2026, 4, 22),
    )

    assert result.staleness_days == 52
    assert result.valuation_score == 44


def test_snapshot_without_positive_multiple_returns_all_metrics_unavailable() -> None:
    result = valuation_anchor.analyze_valuation_anchor_from_snapshot(
        make_snapshot(pe_ratio=None),
        analysis_date=date(2026, 4, 22),
    )

    assert result.primary_metric_used is None
    assert result.primary_metric_value is None
    assert result.primary_metric_selection_reason is None
    assert result.primary_metric_fallback_reason == "AllMetricsUnavailable"
    assert result.historical_percentile is None
    assert result.peer_relative_ratio is None
    assert result.peg_flag == valuation_anchor.PegFlag.NOT_APPLICABLE_PRIMARY_METRIC
    assert result.space_rating == valuation_anchor.SpaceRating.FAIR
    assert result.valuation_score == 36
    assert result.confidence == valuation_anchor.ConfidenceLevel.LOW
    assert result.missing_fields == [
        "valuation_history",
        "peer_multiples",
        "forward_eps_growth_pct_next_12m",
        "pe_ratio",
    ]
    assert result.warnings == [
        valuation_anchor.SNAPSHOT_LIMITATION_WARNING,
        valuation_anchor.SNAPSHOT_NO_METRIC_WARNING,
    ]

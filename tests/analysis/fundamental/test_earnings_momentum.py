from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "analysis"
        / "fundamental"
        / "earnings_momentum.py"
    )
    spec = importlib.util.spec_from_file_location("tradepilot_earnings_momentum", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


earnings_momentum = _load_module()


def _quarter(report_date: date, *, eps_actual: float, eps_consensus: float, revenue_actual: float, revenue_consensus: float):
    return earnings_momentum.EarningsQuarter(
        report_date=report_date,
        eps_actual=eps_actual,
        eps_consensus_pre_report=eps_consensus,
        revenue_actual=revenue_actual,
        revenue_consensus_pre_report=revenue_consensus,
    )


def test_earnings_momentum_accelerating_with_positive_revision_and_guidance():
    dataset = earnings_momentum.EarningsMomentumInput(
        ticker="NVDA",
        analysis_timestamp=datetime(2026, 4, 22, 10, 0, 0),
        quarterly_results=(
            _quarter(date(2026, 3, 31), eps_actual=1.25, eps_consensus=1.00, revenue_actual=112, revenue_consensus=108),
            _quarter(date(2025, 12, 31), eps_actual=1.15, eps_consensus=1.00, revenue_actual=108, revenue_consensus=105),
            _quarter(date(2025, 9, 30), eps_actual=1.05, eps_consensus=0.95, revenue_actual=104, revenue_consensus=102),
            _quarter(date(2025, 6, 30), eps_actual=0.98, eps_consensus=0.92, revenue_actual=101, revenue_consensus=99),
        ),
        revision_summary=earnings_momentum.RevisionSnapshot(
            as_of_date=date(2026, 4, 20),
            eps_up_30d=7,
            eps_down_30d=1,
            eps_up_60d=6,
            eps_down_60d=2,
            revenue_up_30d=5,
            revenue_down_30d=1,
        ),
        current_quarter_consensus=earnings_momentum.CurrentQuarterConsensus(
            as_of_date=date(2026, 4, 20),
            eps_consensus_now=1.40,
            eps_consensus_30d_ago=1.30,
        ),
        guidance_history=(
            earnings_momentum.GuidanceRecord(
                as_of_date=date(2026, 3, 31),
                eps_low=1.45,
                eps_high=1.55,
                revenue_low=118,
                revenue_high=122,
            ),
            earnings_momentum.GuidanceRecord(
                as_of_date=date(2025, 12, 31),
                eps_low=1.30,
                eps_high=1.40,
                revenue_low=112,
                revenue_high=116,
            ),
        ),
    )

    result = earnings_momentum.analyze_earnings_momentum(dataset)

    assert result.metrics.earnings_momentum == "Accelerating"
    assert result.metrics.current_quarter_bar == "High"
    assert result.metrics.guidance_trend == "Raised"
    assert result.metrics.eps_beat_streak_quarters == 4
    assert result.metrics.earnings_score > 80
    assert result.confidence.confidence_level == "High"


def test_earnings_momentum_decelerating_when_guidance_is_lowered():
    dataset = earnings_momentum.EarningsMomentumInput(
        ticker="TSLA",
        analysis_timestamp=datetime(2026, 4, 22, 10, 0, 0),
        quarterly_results=(
            _quarter(date(2026, 3, 31), eps_actual=0.92, eps_consensus=1.00, revenue_actual=98, revenue_consensus=100),
            _quarter(date(2025, 12, 31), eps_actual=0.95, eps_consensus=1.02, revenue_actual=99, revenue_consensus=101),
            _quarter(date(2025, 9, 30), eps_actual=0.96, eps_consensus=1.01, revenue_actual=100, revenue_consensus=102),
            _quarter(date(2025, 6, 30), eps_actual=0.97, eps_consensus=1.00, revenue_actual=101, revenue_consensus=103),
        ),
        revision_summary=earnings_momentum.RevisionSnapshot(
            as_of_date=date(2026, 4, 18),
            eps_up_30d=1,
            eps_down_30d=5,
            eps_up_60d=2,
            eps_down_60d=6,
            revenue_up_30d=1,
            revenue_down_30d=4,
        ),
        current_quarter_consensus=earnings_momentum.CurrentQuarterConsensus(
            as_of_date=date(2026, 4, 18),
            eps_consensus_now=0.88,
            eps_consensus_30d_ago=0.94,
        ),
        guidance_history=(
            earnings_momentum.GuidanceRecord(
                as_of_date=date(2026, 3, 31),
                eps_low=0.80,
                eps_high=0.88,
                revenue_low=94,
                revenue_high=97,
            ),
            earnings_momentum.GuidanceRecord(
                as_of_date=date(2025, 12, 31),
                eps_low=0.95,
                eps_high=1.02,
                revenue_low=99,
                revenue_high=103,
            ),
        ),
    )

    result = earnings_momentum.analyze_earnings_momentum(dataset)

    assert result.metrics.guidance_trend == "Lowered"
    assert result.metrics.earnings_momentum == "Decelerating"
    assert result.metrics.current_quarter_bar == "Low"
    assert result.metrics.earnings_score < 40


def test_earnings_momentum_uses_normalized_scoring_when_revision_data_is_missing():
    dataset = earnings_momentum.EarningsMomentumInput(
        ticker="AMZN",
        analysis_timestamp=datetime(2026, 4, 22, 10, 0, 0),
        quarterly_results=(
            _quarter(date(2026, 3, 31), eps_actual=1.04, eps_consensus=1.00, revenue_actual=105, revenue_consensus=104),
            _quarter(date(2025, 12, 31), eps_actual=0.99, eps_consensus=0.97, revenue_actual=103, revenue_consensus=102),
            _quarter(date(2025, 9, 30), eps_actual=0.95, eps_consensus=0.94, revenue_actual=101, revenue_consensus=100),
            _quarter(date(2025, 6, 30), eps_actual=0.91, eps_consensus=0.90, revenue_actual=100, revenue_consensus=99),
        ),
        current_quarter_consensus=earnings_momentum.CurrentQuarterConsensus(
            as_of_date=date(2026, 4, 19),
            eps_consensus_now=1.08,
            eps_consensus_30d_ago=1.04,
        ),
        guidance_history=(
            earnings_momentum.GuidanceRecord(
                as_of_date=date(2026, 3, 31),
                explicit_no_guidance=True,
            ),
        ),
    )

    result = earnings_momentum.analyze_earnings_momentum(dataset)

    assert result.flags.used_normalized_scoring is True
    assert result.metrics.earnings_momentum == "Stable"
    assert result.metrics.current_quarter_bar == "Normal"
    assert result.metrics.earnings_score < 70
    assert "eps_revision_core" in result.missing_fields
    assert result.confidence.confidence_level in {"Medium", "Low"}

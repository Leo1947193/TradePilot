from __future__ import annotations

from datetime import UTC, date, datetime

from app.analysis.fundamental.aggregate import (
    SINGLE_SNAPSHOT_SUBRESULT_KEY,
    SINGLE_SNAPSHOT_WEIGHT_SCHEME,
    aggregate_fundamental_signals,
    analyze_financial_snapshot,
)
from app.analysis.fundamental.earnings_momentum import (
    EarningsMomentumConfidence,
    EarningsMomentumFlags,
    EarningsMomentumMetrics,
    EarningsMomentumResult,
    EarningsMomentumSubscores,
)
from app.analysis.fundamental.financial_health import FinancialHealthResult
from app.analysis.fundamental.schemas import FundamentalSubmoduleBundle
from app.analysis.fundamental.valuation_anchor import ConfidenceLevel, PegFlag, PeerGroupScope, SpaceRating, ValuationAnchorResult
from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import FinancialSnapshot, ProviderSourceRef


def test_analyze_financial_snapshot_preserves_placeholder_scoring_and_summary() -> None:
    signal = analyze_financial_snapshot(
        FinancialSnapshot(
            symbol="AAPL",
            as_of_date=date(2026, 4, 17),
            currency="USD",
            revenue=100000000.0,
            net_income=25000000.0,
            eps=6.5,
            gross_margin_pct=46.0,
            operating_margin_pct=31.0,
            pe_ratio=28.2,
            market_cap=3000000000.0,
            source=ProviderSourceRef(
                name="yfinance",
                url="https://finance.yahoo.com/quote/AAPL/financials",
                fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
            ),
        )
    )

    assert signal.direction == AnalysisDirection.BULLISH
    assert signal.data_completeness_pct == 100.0
    assert signal.low_confidence is False
    assert signal.positive_signals == 5
    assert signal.negative_signals == 0
    assert signal.summary == (
        "Fundamental analysis reviewed 7 of 7 core fields and found a bullish bias "
        "(positive signals: 5, negative signals: 0). Key fields: market cap 3000000000, "
        "PE 28.20, EPS 6.50."
    )


def test_aggregate_fundamental_signals_wraps_single_snapshot_v1_contract() -> None:
    signal = analyze_financial_snapshot(
        FinancialSnapshot(
            symbol="TSLA",
            as_of_date=date(2026, 4, 17),
            net_income=-1.0,
            eps=-0.5,
            gross_margin_pct=18.0,
            operating_margin_pct=8.0,
            pe_ratio=80.0,
            source=ProviderSourceRef(
                name="yfinance",
                url="https://finance.yahoo.com/quote/TSLA/financials",
                fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
            ),
        )
    )

    aggregate = aggregate_fundamental_signals(signal)

    assert aggregate.fundamental_bias == AnalysisDirection.BEARISH
    assert aggregate.composite_score == -5.0
    assert aggregate.weight_scheme_used == SINGLE_SNAPSHOT_WEIGHT_SCHEME
    assert aggregate.low_confidence is False
    assert aggregate.low_confidence_modules == []
    assert aggregate.subresults[SINGLE_SNAPSHOT_SUBRESULT_KEY] == signal
    assert aggregate.key_risks == ["negative_snapshot_bias"]


def test_aggregate_fundamental_signals_includes_submodules_and_disqualify_bias() -> None:
    signal = analyze_financial_snapshot(
        FinancialSnapshot(
            symbol="TSLA",
            as_of_date=date(2026, 4, 17),
            net_income=5.0,
            eps=1.2,
            gross_margin_pct=25.0,
            operating_margin_pct=12.0,
            pe_ratio=20.0,
            market_cap=1000000000.0,
            source=ProviderSourceRef(
                name="yfinance",
                url="https://finance.yahoo.com/quote/TSLA/financials",
                fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
            ),
        )
    )

    aggregate = aggregate_fundamental_signals(
        signal,
        submodules=FundamentalSubmoduleBundle(
            financial_snapshot=signal,
            financial_health=FinancialHealthResult(
                overall_rating="High",
                disqualify=True,
                hard_risk_reasons=("near_term_debt_coverage_failure",),
                category_ratings={
                    "cashflow_quality": "Low",
                    "liquidity_pressure": "High",
                    "earnings_quality": "Low",
                    "leverage_pressure": "High",
                },
                red_flag_categories=("liquidity_pressure",),
                checks=(),
                health_score=22,
                data_staleness_days=0,
                missing_fields=(),
                low_confidence=False,
                warnings=(),
            ),
            earnings_momentum=EarningsMomentumResult(
                schema_version="1.0",
                ticker="TSLA",
                analysis_timestamp="2026-04-17T00:00:00+00:00",
                module="EarningsMomentumAnalyzerV1",
                staleness_days=0,
                missing_fields=(),
                metrics=EarningsMomentumMetrics(
                    eps_beat_streak_quarters=None,
                    avg_eps_surprise_pct_4q=None,
                    avg_revenue_surprise_pct_4q=None,
                    eps_revision_balance_30d=None,
                    eps_revision_balance_60d=None,
                    revenue_revision_balance_30d=None,
                    guidance_trend=None,
                    current_quarter_bar="Normal",
                    earnings_momentum="Stable",
                    earnings_score=50,
                ),
                subscores=EarningsMomentumSubscores(None, None, None, None),
                confidence=EarningsMomentumConfidence(
                    confidence_score=0.2,
                    confidence_level="Low",
                    critical_missing_fields=(),
                    stale_fields=(),
                ),
                flags=EarningsMomentumFlags(
                    guidance_data_missing=True,
                    used_degraded_quarter_set=True,
                    used_normalized_scoring=True,
                ),
                source_trace=(),
            ),
            valuation_anchor=ValuationAnchorResult(
                as_of_date=date(2026, 4, 17),
                primary_metric_used="ForwardPE",
                primary_metric_value=20.0,
                primary_metric_selection_reason="SnapshotPERatioProxy",
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
                valuation_score=48,
                confidence=ConfidenceLevel.LOW,
                staleness_days=0,
                missing_fields=[],
                low_confidence=True,
                warnings=[],
            ),
        ),
    )

    assert aggregate.fundamental_bias == AnalysisDirection.DISQUALIFIED
    assert "financial_health" in aggregate.subresults
    assert "earnings_momentum" in aggregate.subresults
    assert "valuation_anchor" in aggregate.subresults
    assert "financial_health_disqualify" in aggregate.key_risks
    assert "near_term_debt_coverage_failure" in aggregate.key_risks
    assert "earnings_momentum" in aggregate.low_confidence_modules
    assert "valuation_anchor" in aggregate.low_confidence_modules

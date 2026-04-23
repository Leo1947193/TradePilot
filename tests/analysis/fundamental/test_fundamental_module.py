from __future__ import annotations

from datetime import UTC, date, datetime

from app.analysis.fundamental.module import (
    analyze_fundamental_aggregate,
    analyze_fundamental_module,
)
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus
from app.services.providers.dtos import FinancialSnapshot, ProviderSourceRef


def test_analyze_fundamental_module_maps_aggregate_to_analysis_module_result() -> None:
    snapshot = FinancialSnapshot(
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

    aggregate = analyze_fundamental_aggregate(snapshot)
    result = analyze_fundamental_module(snapshot)

    assert result.module == AnalysisModuleName.FUNDAMENTAL
    assert result.status == ModuleExecutionStatus.USABLE
    assert result.summary == aggregate.subresults["financial_snapshot"].summary
    assert result.direction == aggregate.fundamental_bias
    assert result.data_completeness_pct == aggregate.data_completeness_pct
    assert result.low_confidence == aggregate.subresults["financial_snapshot"].low_confidence
    assert result.reason is None
    assert aggregate.summary != result.summary
    assert aggregate.low_confidence != result.low_confidence


def test_analyze_fundamental_aggregate_builds_integrated_subresults() -> None:
    snapshot = FinancialSnapshot(
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

    aggregate = analyze_fundamental_aggregate(snapshot)

    assert "financial_snapshot" in aggregate.subresults
    assert "financial_health" in aggregate.subresults
    assert "earnings_momentum" in aggregate.subresults
    assert "valuation_anchor" in aggregate.subresults
    assert aggregate.summary

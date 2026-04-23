from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.technical.module import analyze_technical_aggregate, analyze_technical_module
from app.schemas.api import TechnicalSetupState
from app.schemas.modules import AnalysisDirection, AnalysisModuleName, ModuleExecutionStatus
from app.services.providers.dtos import MarketBar, ProviderSourceRef


def make_market_bar(
    *,
    day: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        symbol="AAPL",
        timestamp=datetime(2026, 4, day, 12, 0, tzinfo=UTC),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000000,
        source=ProviderSourceRef(
            name="yfinance",
            url="https://finance.yahoo.com/quote/AAPL/history",
            fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
        ),
    )


def test_analyze_technical_aggregate_returns_internal_contract_fields() -> None:
    aggregate = analyze_technical_aggregate(
        [
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    assert aggregate.technical_signal == AnalysisDirection.BULLISH
    assert aggregate.trend == AnalysisDirection.BULLISH
    assert aggregate.setup_state == TechnicalSetupState.ACTIONABLE
    assert aggregate.volume_pattern == "neutral"
    assert aggregate.key_support == []
    assert aggregate.key_resistance == []
    assert aggregate.subsignals["daily_bars"].direction == AnalysisDirection.BULLISH


def test_analyze_technical_module_maps_aggregate_to_analysis_module_result() -> None:
    result = analyze_technical_module(
        [
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    assert result.module == AnalysisModuleName.TECHNICAL
    assert result.status == ModuleExecutionStatus.USABLE
    assert result.direction == AnalysisDirection.BULLISH
    assert result.summary == (
        "Technical analysis reviewed 3 market bars. Price return over lookback: +3.17%. "
        "Latest close is above the short moving average, producing a bullish bias."
    )
    assert result.data_completeness_pct == 5.0
    assert result.low_confidence is False
    assert result.reason is None

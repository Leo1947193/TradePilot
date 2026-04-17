from __future__ import annotations

from datetime import UTC, datetime

from app.graph.nodes.run_technical import (
    TECHNICAL_DEGRADED_REASON,
    TECHNICAL_DEGRADED_SUMMARY,
    TECHNICAL_DEGRADED_WARNING,
    run_technical,
)
from app.services.providers.dtos import MarketBar, ProviderSourceRef
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_technical_writes_degraded_module_result() -> None:
    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.technical is not None
    assert state.module_results.technical.module == AnalysisModuleName.TECHNICAL
    assert state.module_results.technical.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.technical.low_confidence is True
    assert state.module_results.technical.summary == TECHNICAL_DEGRADED_SUMMARY
    assert state.module_results.technical.reason == TECHNICAL_DEGRADED_REASON


def test_run_technical_updates_diagnostics_without_duplicates() -> None:
    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["technical"]
    assert state.diagnostics.warnings == [TECHNICAL_DEGRADED_WARNING]


def test_run_technical_preserves_unrelated_state() -> None:
    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_789",
            "context": {
                "market": "US",
                "benchmark": "SPY",
                "analysis_window_days": [7, 90],
            },
            "module_results": {
                "fundamental": {
                    "status": "usable",
                    "summary": "Fundamentals remain stable.",
                    "direction": "neutral",
                    "data_completeness_pct": 92,
                }
            },
            "diagnostics": {
                "excluded_modules": ["event"],
                "warnings": ["existing warning"],
            },
        }
    )

    assert state.request_id == "req_789"
    assert state.context.market == "US"
    assert state.module_results.fundamental is not None
    assert state.module_results.fundamental.module == "fundamental"
    assert state.diagnostics.excluded_modules == ["event"]
    assert state.diagnostics.warnings == ["existing warning", TECHNICAL_DEGRADED_WARNING]


def test_run_technical_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_technical(initial_state)
    second_run = run_technical(first_run)

    assert second_run.diagnostics.degraded_modules == ["technical"]
    assert second_run.diagnostics.warnings == [TECHNICAL_DEGRADED_WARNING]
    assert second_run.module_results.technical is not None
    assert second_run.module_results.technical.status == ModuleExecutionStatus.DEGRADED


class FakeMarketDataProvider:
    def __init__(self, bars: list[MarketBar] | None = None, error: Exception | None = None) -> None:
        self.bars = bars or []
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def get_daily_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        self.calls.append((symbol, lookback_days))
        if self.error is not None:
            raise self.error
        return self.bars

    async def get_benchmark_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        return []


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


def test_run_technical_provider_backed_path_writes_usable_result() -> None:
    provider = FakeMarketDataProvider(
        bars=[
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_provider",
            "context": {"analysis_window_days": [7, 90]},
        },
        market_data_provider=provider,
    )

    assert provider.calls == [("AAPL", 90)]
    assert state.module_results.technical is not None
    assert state.module_results.technical.status == ModuleExecutionStatus.USABLE
    assert state.module_results.technical.direction == "bullish"
    assert state.module_results.technical.summary == (
        "Technical analysis reviewed 3 market bars. Price return over lookback: +3.17%. "
        "Latest close is above the short moving average, producing a bullish bias."
    )
    assert state.module_results.technical.data_completeness_pct == 5.0
    assert state.module_results.technical.low_confidence is False
    assert state.diagnostics.degraded_modules == []
    assert state.diagnostics.warnings == []


def test_run_technical_provider_backed_path_appends_source_once() -> None:
    provider = FakeMarketDataProvider(
        bars=[make_market_bar(day=17, open_price=190.0, high=193.0, low=189.0, close=192.0)]
    )

    state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_source",
            "context": {"analysis_window_days": [7, 90]},
            "sources": [
                {
                    "type": "technical",
                    "name": "yfinance",
                    "url": "https://finance.yahoo.com/quote/AAPL/history",
                }
            ],
        },
        market_data_provider=provider,
    )

    assert len(state.sources) == 1
    assert state.sources[0].name == "yfinance"


def test_run_technical_provider_errors_or_empty_data_fall_back_to_degraded() -> None:
    empty_provider = FakeMarketDataProvider(bars=[])
    error_provider = FakeMarketDataProvider(error=RuntimeError("upstream failed"))

    empty_state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_empty",
            "context": {"analysis_window_days": [7, 90]},
        },
        market_data_provider=empty_provider,
    )
    error_state = run_technical(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_error",
            "context": {"analysis_window_days": [7, 90]},
        },
        market_data_provider=error_provider,
    )

    assert empty_state.module_results.technical is not None
    assert empty_state.module_results.technical.status == ModuleExecutionStatus.DEGRADED
    assert error_state.module_results.technical is not None
    assert error_state.module_results.technical.status == ModuleExecutionStatus.DEGRADED

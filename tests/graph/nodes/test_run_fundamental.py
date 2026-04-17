from __future__ import annotations

from datetime import UTC, date, datetime

from app.graph.nodes.run_fundamental import (
    FUNDAMENTAL_DEGRADED_REASON,
    FUNDAMENTAL_DEGRADED_SUMMARY,
    FUNDAMENTAL_DEGRADED_WARNING,
    FUNDAMENTAL_USABLE_SUMMARY,
    run_fundamental,
)
from app.services.providers.dtos import FinancialSnapshot, ProviderSourceRef
from app.schemas.modules import AnalysisModuleName, ModuleExecutionStatus


def test_run_fundamental_writes_degraded_module_result() -> None:
    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.module_results.fundamental is not None
    assert state.module_results.fundamental.module == AnalysisModuleName.FUNDAMENTAL
    assert state.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED
    assert state.module_results.fundamental.low_confidence is True
    assert state.module_results.fundamental.summary == FUNDAMENTAL_DEGRADED_SUMMARY
    assert state.module_results.fundamental.reason == FUNDAMENTAL_DEGRADED_REASON


def test_run_fundamental_updates_diagnostics_without_duplicates() -> None:
    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
        }
    )

    assert state.diagnostics.degraded_modules == ["fundamental"]
    assert state.diagnostics.warnings == [FUNDAMENTAL_DEGRADED_WARNING]


def test_run_fundamental_preserves_unrelated_state() -> None:
    state = run_fundamental(
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
                "technical": {
                    "status": "usable",
                    "summary": "Trend remains constructive.",
                    "direction": "bullish",
                    "data_completeness_pct": 95,
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
    assert state.module_results.technical is not None
    assert state.module_results.technical.module == "technical"
    assert state.diagnostics.excluded_modules == ["event"]
    assert state.diagnostics.warnings == ["existing warning", FUNDAMENTAL_DEGRADED_WARNING]


def test_run_fundamental_is_idempotent_for_diagnostics_markers() -> None:
    initial_state = {
        "request": {"ticker": "AAPL"},
        "normalized_ticker": "AAPL",
        "request_id": "req_repeat",
    }

    first_run = run_fundamental(initial_state)
    second_run = run_fundamental(first_run)

    assert second_run.diagnostics.degraded_modules == ["fundamental"]
    assert second_run.diagnostics.warnings == [FUNDAMENTAL_DEGRADED_WARNING]
    assert second_run.module_results.fundamental is not None
    assert second_run.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED


class FakeFinancialDataProvider:
    def __init__(
        self,
        snapshot: FinancialSnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls: list[str] = []

    async def get_financial_snapshot(self, symbol: str) -> FinancialSnapshot | None:
        self.calls.append(symbol)
        if self.error is not None:
            raise self.error
        return self.snapshot


def make_snapshot() -> FinancialSnapshot:
    return FinancialSnapshot(
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


def test_run_fundamental_provider_backed_path_writes_usable_result() -> None:
    provider = FakeFinancialDataProvider(snapshot=make_snapshot())

    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_provider",
        },
        financial_data_provider=provider,
    )

    assert provider.calls == ["AAPL"]
    assert state.module_results.fundamental is not None
    assert state.module_results.fundamental.status == ModuleExecutionStatus.USABLE
    assert state.module_results.fundamental.direction == "neutral"
    assert state.module_results.fundamental.summary.startswith(FUNDAMENTAL_USABLE_SUMMARY)
    assert state.module_results.fundamental.low_confidence is False
    assert state.diagnostics.degraded_modules == []
    assert state.diagnostics.warnings == []


def test_run_fundamental_provider_backed_path_appends_source_once() -> None:
    provider = FakeFinancialDataProvider(snapshot=make_snapshot())

    state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_source",
            "sources": [
                {
                    "type": "financial",
                    "name": "yfinance",
                    "url": "https://finance.yahoo.com/quote/AAPL/financials",
                }
            ],
        },
        financial_data_provider=provider,
    )

    assert len(state.sources) == 1
    assert state.sources[0].name == "yfinance"


def test_run_fundamental_provider_errors_or_missing_snapshot_fall_back_to_degraded() -> None:
    missing_provider = FakeFinancialDataProvider(snapshot=None)
    error_provider = FakeFinancialDataProvider(error=RuntimeError("upstream failed"))

    missing_state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_missing",
        },
        financial_data_provider=missing_provider,
    )
    error_state = run_fundamental(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_error",
        },
        financial_data_provider=error_provider,
    )

    assert missing_state.module_results.fundamental is not None
    assert missing_state.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED
    assert error_state.module_results.fundamental is not None
    assert error_state.module_results.fundamental.status == ModuleExecutionStatus.DEGRADED

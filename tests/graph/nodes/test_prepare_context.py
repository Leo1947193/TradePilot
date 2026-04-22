from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.graph.nodes.prepare_context import prepare_context
from app.rules.messages import PREPARE_CONTEXT_NORMALIZED_TICKER_REQUIRED_ERROR
from app.rules.runtime import DEFAULT_ANALYSIS_WINDOW_DAYS, DEFAULT_BENCHMARK, DEFAULT_MARKET
from app.schemas.graph_state import TradePilotState


def test_prepare_context_populates_defaults_for_normalized_ticker() -> None:
    state = prepare_context(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_123",
        }
    )

    assert state.context.market == DEFAULT_MARKET
    assert state.context.benchmark == DEFAULT_BENCHMARK
    assert state.context.analysis_window_days == DEFAULT_ANALYSIS_WINDOW_DAYS
    assert state.context.analysis_time is not None
    assert state.context.analysis_time.tzinfo == timezone.utc


def test_prepare_context_preserves_non_context_fields() -> None:
    state = prepare_context(
        {
            "request": {"ticker": "AAPL"},
            "normalized_ticker": "AAPL",
            "request_id": "req_456",
            "sources": [
                {
                    "type": "technical",
                    "name": "yfinance",
                    "url": "https://finance.yahoo.com/quote/AAPL/history",
                }
            ],
            "diagnostics": {"warnings": ["existing warning"]},
        }
    )

    assert state.request.ticker == "AAPL"
    assert state.request_id == "req_456"
    assert state.sources[0].name == "yfinance"
    assert state.diagnostics.warnings == ["existing warning"]


@pytest.mark.parametrize(
    "normalized_ticker",
    [
        None,
        "",
        "   ",
    ],
)
def test_prepare_context_fails_fast_for_missing_or_blank_normalized_ticker(
    normalized_ticker: str | None,
) -> None:
    with pytest.raises(ValueError, match=PREPARE_CONTEXT_NORMALIZED_TICKER_REQUIRED_ERROR):
        prepare_context(
            {
                "request": {"ticker": "AAPL"},
                "normalized_ticker": normalized_ticker,
                "request_id": "req_789",
            }
        )


def test_prepare_context_preserves_existing_valid_context_values() -> None:
    existing_time = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)

    state = prepare_context(
        {
            "request": {"ticker": "MSFT"},
            "normalized_ticker": "MSFT",
            "request_id": "req_999",
            "context": {
                "analysis_time": existing_time.isoformat(),
                "market": "US",
                "benchmark": "QQQ",
                "analysis_window_days": [14, 60],
            },
        }
    )

    assert state.context.analysis_time == existing_time
    assert state.context.market == "US"
    assert state.context.benchmark == "QQQ"
    assert state.context.analysis_window_days == (14, 60)

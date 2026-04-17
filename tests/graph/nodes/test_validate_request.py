from __future__ import annotations

import pytest

from app.graph.nodes.validate_request import validate_request
from app.schemas.api import AnalyzeRequest
from app.schemas.graph_state import TradePilotState


def test_validate_request_normalizes_ticker() -> None:
    state = validate_request(
        {
            "request": {"ticker": "  aapl  "},
            "request_id": "req_123",
        }
    )

    assert state.request.ticker == "AAPL"
    assert state.normalized_ticker == "AAPL"


def test_validate_request_preserves_existing_request_id() -> None:
    state = validate_request(
        {
            "request": {"ticker": "msft"},
            "request_id": "req_existing",
        }
    )

    assert state.request_id == "req_existing"


def test_validate_request_generates_request_id_for_blank_or_missing_values() -> None:
    missing_request_id_state = validate_request({"request": {"ticker": "nvda"}})
    blank_request_id_state = validate_request(
        {
            "request": {"ticker": "tsla"},
            "request_id": "   ",
        }
    )

    assert missing_request_id_state.request_id
    assert blank_request_id_state.request_id
    assert missing_request_id_state.request_id != "   "
    assert blank_request_id_state.request_id != "   "


def test_validate_request_fails_fast_for_blank_ticker_after_normalization() -> None:
    invalid_state = TradePilotState.model_construct(
        request=AnalyzeRequest.model_construct(ticker="   "),
        request_id="req_invalid",
    )

    with pytest.raises(ValueError, match="request ticker must not be blank after normalization"):
        validate_request(invalid_state)

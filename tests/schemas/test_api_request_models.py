from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.api import AnalyzeRequest, ErrorResponse


def test_analyze_request_requires_ticker() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalyzeRequest.model_validate({})

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "missing",
            "loc": ("ticker",),
            "msg": "Field required",
            "input": {},
        }
    ]


def test_analyze_request_trims_ticker_and_rejects_blank_after_trim() -> None:
    request = AnalyzeRequest.model_validate({"ticker": "  AAPL  "})

    assert request.ticker == "AAPL"

    with pytest.raises(ValidationError) as exc_info:
        AnalyzeRequest.model_validate({"ticker": "   "})

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "string_too_short",
            "loc": ("ticker",),
            "msg": "String should have at least 1 character",
            "input": "   ",
            "ctx": {"min_length": 1},
        }
    ]


def test_analyze_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalyzeRequest.model_validate({"ticker": "AAPL", "exchange": "NASDAQ"})

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "extra_forbidden",
            "loc": ("exchange",),
            "msg": "Extra inputs are not permitted",
            "input": "NASDAQ",
        }
    ]


def test_error_response_shape_stays_nested_under_error() -> None:
    payload = ErrorResponse.model_validate(
        {
            "error": {
                "code": "invalid_request",
                "message": "ticker is required",
                "details": [{"field": "ticker", "reason": "missing"}],
            }
        }
    )

    assert payload.model_dump(exclude_none=True) == {
        "error": {
            "code": "invalid_request",
            "message": "ticker is required",
            "details": [{"field": "ticker", "reason": "missing"}],
        }
    }


def test_error_response_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ErrorResponse.model_validate(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "ticker is required",
                },
                "status": 400,
            }
        )

    assert exc_info.value.errors(include_url=False) == [
        {
            "type": "extra_forbidden",
            "loc": ("status",),
            "msg": "Extra inputs are not permitted",
            "input": 400,
        }
    ]

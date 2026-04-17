from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_post_analyses_route_exists() -> None:
    route = next(
        (
            candidate
            for candidate in app.routes
            if candidate.path == "/api/v1/analyses" and "POST" in getattr(candidate, "methods", set())
        ),
        None,
    )

    assert route is not None


def test_valid_request_returns_placeholder_internal_error() -> None:
    response = client.post("/api/v1/analyses", json={"ticker": "AAPL"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "analysis pipeline is not implemented",
        }
    }


def test_missing_ticker_returns_documented_400_error_shape() -> None:
    response = client.post("/api/v1/analyses", json={})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "ticker is required",
            "details": [{"field": "ticker", "reason": "missing"}],
        }
    }
    assert "detail" not in response.json()


def test_extra_field_returns_documented_400_error_shape() -> None:
    response = client.post("/api/v1/analyses", json={"ticker": "AAPL", "exchange": "NASDAQ"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "request contains invalid fields",
            "details": [{"field": "exchange", "reason": "extra_forbidden"}],
        }
    }
    assert "detail" not in response.json()


def test_openapi_exposes_only_the_business_endpoint() -> None:
    schema = app.openapi()

    assert list(schema["paths"]) == ["/api/v1/analyses"]

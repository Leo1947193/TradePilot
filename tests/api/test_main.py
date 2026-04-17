from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.main import app, get_analysis_report_repository
from app.config import get_settings
from app.repositories.analysis_reports import AnalysisReportPayload, PersistedAnalysisRecord
from app.schemas.api import AnalysisResponse


@dataclass
class FakeAnalysisReportRepository:
    captured_payload: AnalysisReportPayload | None = None

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        self.captured_payload = payload
        return PersistedAnalysisRecord(
            record_id="report_api_123",
            persisted_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        )


def make_client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)


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


def test_valid_request_returns_documented_503_when_repository_is_unavailable() -> None:
    with make_client() as client:
        response = client.post("/api/v1/analyses", json={"ticker": "AAPL"})

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "upstream_unavailable",
            "message": "analysis persistence is unavailable",
        }
    }


def test_valid_request_returns_200_with_dependency_override() -> None:
    repository = FakeAnalysisReportRepository()
    app.dependency_overrides[get_analysis_report_repository] = lambda: repository

    try:
        with make_client() as client:
            response = client.post("/api/v1/analyses", json={"ticker": "AAPL"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    analysis_response = AnalysisResponse.model_validate(payload)
    assert analysis_response.ticker == "AAPL"
    assert analysis_response.trade_plan.overall_bias == analysis_response.decision_synthesis.overall_bias
    assert repository.captured_payload is not None
    assert repository.captured_payload.response.ticker == "AAPL"


def test_missing_ticker_returns_documented_400_error_shape() -> None:
    with make_client() as client:
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
    with make_client() as client:
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

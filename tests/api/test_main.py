from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.main import app, get_analysis_report_repository
from app.config import get_settings
from app.repositories.analysis_reports import AnalysisReportPayload, PersistedAnalysisRecord
from app.schemas.api import AnalysisResponse
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent, ProviderSourceRef
from app.services.providers.dtos import FinancialSnapshot, MarketBar


@dataclass
class FakeAnalysisReportRepository:
    captured_payload: AnalysisReportPayload | None = None

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        self.captured_payload = payload
        return PersistedAnalysisRecord(
            record_id="report_api_123",
            persisted_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        )


class FakeCompanyEventsProvider:
    async def get_company_events(self, symbol: str, *, days_ahead: int) -> list[CompanyEvent]:
        return [
            CompanyEvent(
                symbol=symbol,
                event_type="earnings",
                title=f"{symbol} earnings",
                scheduled_at=datetime(2026, 4, 20, 20, 30, tzinfo=UTC),
                category="company",
                source=ProviderSourceRef(
                    name="company-events-provider",
                    url="https://example.com/company-events",
                    fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                ),
            )
        ]


class FakeMacroCalendarProvider:
    async def get_macro_events(self, *, market: str, days_ahead: int) -> list[MacroCalendarEvent]:
        return [
            MacroCalendarEvent(
                event_name="CPI",
                country=market,
                category="inflation",
                scheduled_at=datetime(2026, 4, 18, 12, 30, tzinfo=UTC),
                importance="high",
                source=ProviderSourceRef(
                    name="macro-calendar-provider",
                    url="https://example.com/macro-calendar",
                    fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                ),
            )
        ]


class FakeMarketDataProvider:
    async def get_daily_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        return [
            MarketBar(
                symbol=symbol,
                timestamp=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                open=190.0,
                high=193.0,
                low=189.0,
                close=192.0,
                volume=1000000,
                source=ProviderSourceRef(
                    name="market-data-provider",
                    url="https://example.com/market-data",
                    fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                ),
            )
        ]

    async def get_benchmark_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        return []


class FakeFinancialDataProvider:
    async def get_financial_snapshot(self, symbol: str) -> FinancialSnapshot | None:
        return FinancialSnapshot(
            symbol=symbol,
            as_of_date=datetime(2026, 4, 17, 12, 0, tzinfo=UTC).date(),
            currency="USD",
            revenue=100000000.0,
            net_income=25000000.0,
            eps=6.5,
            gross_margin_pct=46.0,
            operating_margin_pct=31.0,
            pe_ratio=28.2,
            market_cap=3000000000.0,
            source=ProviderSourceRef(
                name="financial-data-provider",
                url="https://example.com/financial-data",
                fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ),
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


def test_valid_request_uses_event_providers_when_present_on_app_state() -> None:
    repository = FakeAnalysisReportRepository()
    app.dependency_overrides[get_analysis_report_repository] = lambda: repository

    try:
        with make_client() as client:
            client.app.state.company_events_provider = FakeCompanyEventsProvider()
            client.app.state.macro_calendar_provider = FakeMacroCalendarProvider()
            response = client.post("/api/v1/analyses", json={"ticker": "AAPL"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = AnalysisResponse.model_validate(response.json())
    assert [source.name for source in payload.sources] == [
        "company-events-provider",
        "macro-calendar-provider",
    ]


def test_valid_request_uses_market_and_financial_providers_when_present_on_app_state() -> None:
    repository = FakeAnalysisReportRepository()
    app.dependency_overrides[get_analysis_report_repository] = lambda: repository

    try:
        with make_client() as client:
            client.app.state.market_data_provider = FakeMarketDataProvider()
            client.app.state.financial_data_provider = FakeFinancialDataProvider()
            response = client.post("/api/v1/analyses", json={"ticker": "AAPL"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = AnalysisResponse.model_validate(response.json())
    assert [source.name for source in payload.sources] == [
        "market-data-provider",
        "financial-data-provider",
    ]


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

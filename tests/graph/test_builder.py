from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.graph.builder import build_analysis_graph
from app.graph.nodes.run_event import EVENT_DEGRADED_WARNING
from app.graph.nodes.run_fundamental import FUNDAMENTAL_DEGRADED_WARNING
from app.graph.nodes.run_sentiment import SENTIMENT_DEGRADED_WARNING
from app.graph.nodes.run_technical import TECHNICAL_DEGRADED_WARNING
from app.repositories.analysis_reports import AnalysisReportPayload, PersistedAnalysisRecord
from app.schemas.graph_state import PersistenceStatus, TradePilotState
from app.services.providers.dtos import (
    CompanyEvent,
    FinancialSnapshot,
    MacroCalendarEvent,
    MarketBar,
    NewsArticle,
    ProviderSourceRef,
)


@dataclass
class FakeAnalysisReportRepository:
    captured_payload: AnalysisReportPayload | None = None

    def save_analysis_report(self, payload: AnalysisReportPayload) -> PersistedAnalysisRecord:
        self.captured_payload = payload
        return PersistedAnalysisRecord(
            record_id="report_graph_123",
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
                name="financial-data-provider",
                url="https://example.com/financial-data",
                fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ),
        )


class FakeNewsDataProvider:
    async def get_company_news(self, symbol: str, *, limit: int) -> list[NewsArticle]:
        return [
            NewsArticle(
                symbol=symbol,
                title=f"{symbol} trades quietly before catalyst",
                published_at=datetime(2026, 4, 17, 11, 30, tzinfo=UTC),
                source_name="Example News",
                url="https://example.com/news",
                summary="Coverage remains balanced ahead of the next catalyst.",
                category="company",
                source=ProviderSourceRef(
                    name="news-data-provider",
                    url="https://example.com/news",
                    fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                ),
            )
        ]


def test_build_analysis_graph_runs_end_to_end() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(repository)

    result = graph.invoke({"request": {"ticker": " aapl "}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.normalized_ticker == "AAPL"
    assert final_state.decision_synthesis is not None
    assert final_state.trade_plan is not None
    assert final_state.response is not None
    assert final_state.persistence.status == PersistenceStatus.SUCCEEDED
    assert final_state.persistence.record_id == "report_graph_123"
    assert final_state.module_results.technical is not None
    assert final_state.module_results.fundamental is not None
    assert final_state.module_results.sentiment is not None
    assert final_state.module_results.event is not None
    assert repository.captured_payload is not None
    assert repository.captured_payload.response == final_state.response


def test_build_analysis_graph_merges_degraded_diagnostics_in_module_order() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(repository)

    result = graph.invoke({"request": {"ticker": " aapl "}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.diagnostics.degraded_modules == [
        "technical",
        "fundamental",
        "sentiment",
        "event",
    ]
    assert final_state.diagnostics.warnings == [
        TECHNICAL_DEGRADED_WARNING,
        FUNDAMENTAL_DEGRADED_WARNING,
        SENTIMENT_DEGRADED_WARNING,
        EVENT_DEGRADED_WARNING,
    ]


def test_build_analysis_graph_topology_matches_v1_order() -> None:
    graph = build_analysis_graph(FakeAnalysisReportRepository())
    topology = graph.get_graph()
    edges = {(edge.source, edge.target) for edge in topology.edges}

    assert ("__start__", "validate_request") in edges
    assert ("validate_request", "prepare_context") in edges
    assert ("prepare_context", "run_technical") in edges
    assert ("prepare_context", "run_fundamental") in edges
    assert ("prepare_context", "run_sentiment") in edges
    assert ("prepare_context", "run_event") in edges
    assert ("run_technical", "synthesize_decision") in edges
    assert ("run_fundamental", "synthesize_decision") in edges
    assert ("run_sentiment", "synthesize_decision") in edges
    assert ("run_event", "synthesize_decision") in edges
    assert ("synthesize_decision", "generate_trade_plan") in edges
    assert ("generate_trade_plan", "assemble_response") in edges
    assert ("assemble_response", "persist_analysis") in edges
    assert ("persist_analysis", "__end__") in edges


def test_build_analysis_graph_supports_provider_backed_event_node() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(
        repository,
        company_events_provider=FakeCompanyEventsProvider(),
        macro_calendar_provider=FakeMacroCalendarProvider(),
    )

    result = graph.invoke({"request": {"ticker": "aapl"}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.module_results.event is not None
    assert final_state.module_results.event.status.value == "usable"
    assert [source.name for source in final_state.sources] == [
        "company-events-provider",
        "macro-calendar-provider",
    ]


def test_build_analysis_graph_supports_provider_backed_technical_and_fundamental_nodes() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(
        repository,
        market_data_provider=FakeMarketDataProvider(),
        financial_data_provider=FakeFinancialDataProvider(),
    )

    result = graph.invoke({"request": {"ticker": "aapl"}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.module_results.technical is not None
    assert final_state.module_results.technical.status.value == "usable"
    assert final_state.module_results.fundamental is not None
    assert final_state.module_results.fundamental.status.value == "usable"
    assert [source.name for source in final_state.sources] == [
        "market-data-provider",
        "financial-data-provider",
    ]


def test_build_analysis_graph_supports_provider_backed_sentiment_node() -> None:
    repository = FakeAnalysisReportRepository()
    graph = build_analysis_graph(
        repository,
        news_data_provider=FakeNewsDataProvider(),
    )

    result = graph.invoke({"request": {"ticker": "aapl"}})
    final_state = TradePilotState.model_validate(result)

    assert final_state.module_results.sentiment is not None
    assert final_state.module_results.sentiment.status.value == "usable"
    assert [source.name for source in final_state.sources] == ["news-data-provider"]

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from app.services.providers.finnhub_news_provider import FinnhubNewsProvider


class FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, params: dict) -> FakeResponse:
        self.calls.append((url, params))
        return FakeResponse(self.payload)


def test_finnhub_news_provider_maps_and_limits_articles() -> None:
    client = FakeAsyncClient(
        [
            {
                "headline": "Second item",
                "datetime": int(datetime(2026, 4, 17, 10, 0, tzinfo=UTC).timestamp()),
                "source": "Reuters",
                "url": "https://example.com/second",
                "summary": "Second summary",
                "category": "company",
            },
            {
                "headline": "Newest item",
                "datetime": int(datetime(2026, 4, 17, 12, 0, tzinfo=UTC).timestamp()),
                "source": "Bloomberg",
                "url": "https://example.com/newest",
                "summary": "Newest summary",
                "category": "product",
            },
        ]
    )
    provider = FinnhubNewsProvider(
        "demo-key",
        client=client,  # type: ignore[arg-type]
        now_provider=lambda: datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
    )

    articles = asyncio.run(provider.get_company_news("aapl", limit=1))

    assert len(articles) == 1
    assert articles[0].title == "Newest item"
    assert articles[0].symbol == "AAPL"
    assert articles[0].source.name == "finnhub"
    assert client.calls[0][0].endswith("/company-news")
    assert client.calls[0][1]["symbol"] == "AAPL"
    assert client.calls[0][1]["token"] == "demo-key"


def test_finnhub_news_provider_uses_configured_window_dates() -> None:
    client = FakeAsyncClient([])
    provider = FinnhubNewsProvider(
        "demo-key",
        client=client,  # type: ignore[arg-type]
        now_provider=lambda: datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
    )

    asyncio.run(provider.get_company_news("msft", limit=5))

    params = client.calls[0][1]
    assert params["from"] == "2026-03-18"
    assert params["to"] == "2026-04-17"


def test_finnhub_news_provider_propagates_http_errors() -> None:
    class ErrorClient(FakeAsyncClient):
        async def get(self, url: str, params: dict) -> FakeResponse:
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("GET", url),
                response=httpx.Response(503, request=httpx.Request("GET", url)),
            )

    provider = FinnhubNewsProvider(
        "demo-key",
        client=ErrorClient([]),  # type: ignore[arg-type]
        now_provider=lambda: datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
    )

    try:
        asyncio.run(provider.get_company_news("aapl", limit=5))
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 503
    else:
        raise AssertionError("expected HTTPStatusError to propagate")

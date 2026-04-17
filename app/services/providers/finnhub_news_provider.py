from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import AsyncIterator

import httpx

from app.services.providers.dtos import NewsArticle, ProviderSourceRef


class FinnhubNewsProvider:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://finnhub.io/api/v1",
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
        now_provider=None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def get_company_news(self, symbol: str, *, limit: int) -> list[NewsArticle]:
        fetched_at = self._now_provider()
        from_date = (fetched_at.date() - timedelta(days=30)).isoformat()
        to_date = fetched_at.date().isoformat()

        async with self._get_client() as client:
            response = await client.get(
                f"{self._base_url}/company-news",
                params={
                    "symbol": symbol.upper(),
                    "from": from_date,
                    "to": to_date,
                    "token": self._api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()

        articles = [
            NewsArticle(
                symbol=symbol.upper(),
                title=item["headline"],
                published_at=datetime.fromtimestamp(item["datetime"], tz=UTC),
                source_name=item["source"],
                url=item["url"],
                summary=item.get("summary"),
                category=item.get("category"),
                source=ProviderSourceRef(
                    name="finnhub",
                    url="https://finnhub.io",
                    fetched_at=fetched_at,
                ),
            )
            for item in payload
        ]
        articles.sort(key=lambda article: article.published_at, reverse=True)
        return articles[:limit]

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            yield client

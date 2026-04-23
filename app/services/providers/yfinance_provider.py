from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from app.services.providers.dtos import (
    CompanyEvent,
    FinancialSnapshot,
    MarketBar,
    ProviderSourceRef,
)


class YFinanceProvider:
    def __init__(self) -> None:
        self._source_name = "yfinance"
        self._source_url = "https://finance.yahoo.com"

    async def get_daily_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        return await asyncio.to_thread(self._get_daily_bars_sync, symbol, lookback_days)

    async def get_benchmark_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        return await self.get_daily_bars(symbol, lookback_days=lookback_days)

    async def get_financial_snapshot(self, symbol: str) -> FinancialSnapshot | None:
        return await asyncio.to_thread(self._get_financial_snapshot_sync, symbol)

    async def get_company_events(self, symbol: str, *, days_ahead: int) -> list[CompanyEvent]:
        return await asyncio.to_thread(self._get_company_events_sync, symbol, days_ahead)

    def _get_daily_bars_sync(self, symbol: str, lookback_days: int) -> list[MarketBar]:
        history = self._normalize_history(self._download_history(symbol, lookback_days), symbol)
        if history is None or history.empty:
            return []

        fetched_at = datetime.now(UTC)
        bars: list[MarketBar] = []
        for timestamp, row in history.iterrows():
            bars.append(
                MarketBar(
                    symbol=symbol.upper(),
                    timestamp=_to_utc_datetime(timestamp),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    source=self._build_source_ref(fetched_at),
                )
            )

        return bars

    def _get_financial_snapshot_sync(self, symbol: str) -> FinancialSnapshot | None:
        ticker = self._get_ticker(symbol)
        info = getattr(ticker, "info", None)
        if not isinstance(info, dict) or not info:
            return None

        fetched_at = datetime.now(UTC)
        as_of_date = date.today()
        earnings_date = self._extract_calendar_datetime(getattr(ticker, "calendar", None))
        if earnings_date is not None:
            as_of_date = earnings_date.date()

        return FinancialSnapshot(
            symbol=symbol.upper(),
            as_of_date=as_of_date,
            currency=info.get("currency"),
            revenue=_as_float(info.get("totalRevenue")),
            net_income=_as_float(info.get("netIncomeToCommon")),
            eps=_as_float(info.get("trailingEps")),
            gross_margin_pct=_ratio_to_pct(info.get("grossMargins")),
            operating_margin_pct=_ratio_to_pct(info.get("operatingMargins")),
            pe_ratio=_as_float(info.get("trailingPE")),
            market_cap=_as_float(info.get("marketCap")),
            source=self._build_source_ref(fetched_at),
        )

    def _get_company_events_sync(self, symbol: str, days_ahead: int) -> list[CompanyEvent]:
        ticker = self._get_ticker(symbol)
        scheduled_at = self._extract_calendar_datetime(getattr(ticker, "calendar", None))
        if scheduled_at is None:
            return []

        now = datetime.now(UTC)
        cutoff = now + timedelta(days=days_ahead)
        if scheduled_at < now or scheduled_at > cutoff:
            return []

        return [
            CompanyEvent(
                symbol=symbol.upper(),
                event_type="earnings",
                title=f"{symbol.upper()} earnings",
                scheduled_at=scheduled_at,
                category="company",
                source=self._build_source_ref(now),
            )
        ]

    def _download_history(self, symbol: str, lookback_days: int) -> pd.DataFrame:
        return yf.download(
            tickers=symbol,
            period=f"{max(lookback_days, 1)}d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )

    def _normalize_history(self, history: pd.DataFrame | None, symbol: str) -> pd.DataFrame | None:
        if history is None or history.empty:
            return history

        if not isinstance(history.columns, pd.MultiIndex):
            return history

        ticker_symbol = symbol.upper()
        if "Ticker" in history.columns.names:
            available_tickers = history.columns.get_level_values("Ticker")
        else:
            available_tickers = history.columns.get_level_values(-1)

        if ticker_symbol in available_tickers:
            normalized_history = history.xs(ticker_symbol, axis=1, level=-1)
        else:
            normalized_history = history.droplevel(-1, axis=1)

        normalized_history.columns.name = None
        return normalized_history

    def _get_ticker(self, symbol: str):
        return yf.Ticker(symbol)

    def _build_source_ref(self, fetched_at: datetime) -> ProviderSourceRef:
        return ProviderSourceRef(
            name=self._source_name,
            url=self._source_url,
            fetched_at=fetched_at,
        )

    def _extract_calendar_datetime(self, calendar: Any) -> datetime | None:
        if calendar is None:
            return None

        if isinstance(calendar, dict):
            earnings_date = calendar.get("Earnings Date")
            return _coerce_first_datetime(earnings_date)

        if isinstance(calendar, pd.DataFrame):
            if "Earnings Date" in calendar.index:
                return _coerce_first_datetime(calendar.loc["Earnings Date"].iloc[0])
            if "Earnings Date" in calendar.columns:
                return _coerce_first_datetime(calendar["Earnings Date"].iloc[0])

        return None


def _to_utc_datetime(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    return timestamp.to_pydatetime()


def _coerce_first_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            result = _coerce_first_datetime(item)
            if result is not None:
                return result
        return None
    if isinstance(value, pd.Series):
        return _coerce_first_datetime(value.iloc[0] if not value.empty else None)
    return _to_utc_datetime(value)


def _ratio_to_pct(value: Any) -> float | None:
    numeric = _as_float(value)
    if numeric is None:
        return None
    return numeric * 100


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)

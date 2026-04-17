from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class ProviderDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderSourceRef(ProviderDto):
    name: str
    url: AnyUrl | None = None
    fetched_at: datetime

    @field_validator("fetched_at")
    @classmethod
    def ensure_fetched_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc_datetime(value, field_name="fetched_at")


class MarketBar(ProviderDto):
    symbol: str
    timeframe: str = "1d"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: ProviderSourceRef

    @field_validator("timestamp")
    @classmethod
    def ensure_timestamp_is_utc(cls, value: datetime) -> datetime:
        return _require_utc_datetime(value, field_name="timestamp")


class FinancialSnapshot(ProviderDto):
    symbol: str
    as_of_date: date
    currency: str | None = None
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    gross_margin_pct: float | None = Field(default=None, ge=0, le=100)
    operating_margin_pct: float | None = Field(default=None, ge=0, le=100)
    pe_ratio: float | None = None
    market_cap: float | None = None
    source: ProviderSourceRef


class CompanyEvent(ProviderDto):
    symbol: str
    event_type: str
    title: str
    scheduled_at: datetime
    category: str | None = None
    url: AnyUrl | None = None
    source: ProviderSourceRef

    @field_validator("scheduled_at")
    @classmethod
    def ensure_scheduled_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc_datetime(value, field_name="scheduled_at")


class NewsArticle(ProviderDto):
    symbol: str
    title: str
    published_at: datetime
    source_name: str
    url: AnyUrl
    summary: str | None = None
    category: str | None = None
    source: ProviderSourceRef

    @field_validator("published_at")
    @classmethod
    def ensure_published_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc_datetime(value, field_name="published_at")


class MacroCalendarEvent(ProviderDto):
    event_name: str
    country: str
    category: str
    scheduled_at: datetime
    importance: str | None = None
    source: ProviderSourceRef

    @field_validator("scheduled_at")
    @classmethod
    def ensure_scheduled_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc_datetime(value, field_name="scheduled_at")


def _require_utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")

    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")

    return value

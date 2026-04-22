from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AnyUrl, ConfigDict

from app.schemas.modules import AnalysisDirection, ModuleSchema


class EventStatus(StrEnum):
    SCHEDULED = "scheduled"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    RUMORED = "rumored"


class EventDirectionHint(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    BINARY = "binary"
    UNKNOWN = "unknown"


class EarningsWindowState(StrEnum):
    NONE = "none"
    WITHIN_3D = "within_3d"
    WITHIN_14D = "within_14d"
    WITHIN_90D = "within_90d"


class EventSourceTraceEntry(ModuleSchema):
    dataset: str
    source: str
    source_url: AnyUrl | None = None
    fetched_at: datetime
    staleness_days: int = 0
    missing_fields: tuple[str, ...] = ()
    record_count: int = 1


class ScheduledEventRecord(ModuleSchema):
    event_id: str | None = None
    symbol: str | None = None
    event_type: str
    title: str
    scheduled_at: datetime
    category: str | None = None
    url: AnyUrl | None = None
    event_status: EventStatus
    event_state: str | None = None
    direction_hint: EventDirectionHint
    earnings_session: str | None = None
    days_until: float
    source_trace: tuple[EventSourceTraceEntry, ...]


class ScheduledCatalyst(ModuleSchema):
    event_id: str
    event_type: str
    title: str
    scheduled_at: datetime
    event_status: EventStatus
    direction_hint: EventDirectionHint
    source_url: AnyUrl | None = None


class ScheduledRiskEvent(ModuleSchema):
    event_id: str
    event_type: str
    title: str
    scheduled_at: datetime
    event_status: EventStatus
    risk_label: str
    source_url: AnyUrl | None = None


class ScheduledEventsResult(ModuleSchema):
    upcoming_catalysts: list[str]
    risk_events: list[str]
    event_risk_flags: list[str]
    confirmed_positive_catalysts: int
    confirmed_negative_events: int
    days_to_next_earnings: int | None = None
    earnings_window_state: EarningsWindowState = EarningsWindowState.NONE
    scheduled_catalysts: tuple[ScheduledCatalyst, ...] = ()
    near_term_scheduled_risks: tuple[ScheduledRiskEvent, ...] = ()
    data_completeness_pct: float
    low_confidence: bool
    records: tuple[ScheduledEventRecord, ...]
    normalized_events: tuple[ScheduledEventRecord, ...] = ()
    source_trace: tuple[EventSourceTraceEntry, ...] = ()
    warnings: tuple[str, ...] = ()


class MacroSensitivityEvent(ModuleSchema):
    event_name: str
    category: str
    scheduled_at: datetime
    importance: str | None = None
    days_until: float
    high_sensitivity: bool
    source_trace: tuple[EventSourceTraceEntry, ...]


class MacroSensitivityResult(ModuleSchema):
    risk_events: list[str]
    event_risk_flags: list[str]
    macro_event_exposure: str
    data_completeness_pct: float
    low_confidence: bool
    records: tuple[MacroSensitivityEvent, ...]


class CompanyCatalystRecord(ModuleSchema):
    event_type: str
    title: str
    scheduled_at: datetime
    category: str | None = None
    event_state: str
    direction_hint: str
    days_until: float
    source_trace: tuple[EventSourceTraceEntry, ...]


class CompanyCatalystsResult(ModuleSchema):
    upcoming_catalysts: list[str]
    risk_events: list[str]
    event_risk_flags: list[str]
    confirmed_positive_catalysts: int
    confirmed_negative_events: int
    binary_event_count: int
    data_completeness_pct: float
    low_confidence: bool
    records: tuple[CompanyCatalystRecord, ...]


class EventSignal(ModuleSchema):
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


class EventAggregateResult(ModuleSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_bias: AnalysisDirection
    upcoming_catalysts: list[str]
    risk_events: list[str]
    event_risk_flags: list[str]
    data_completeness_pct: float
    low_confidence: bool
    low_confidence_modules: list[str]
    weight_scheme_used: str
    subresults: dict[str, Any]
    summary: str

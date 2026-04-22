from __future__ import annotations

from app.analysis.event.aggregate import aggregate_event_signals
from app.analysis.event.company_catalysts import analyze_company_catalysts
from app.analysis.event.macro_sensitivity import analyze_macro_sensitivity
from app.analysis.event.module import (
    analyze_event_aggregate,
    analyze_event_inputs,
    analyze_event_module,
)
from app.analysis.event.scheduled_events import analyze_scheduled_events
from app.analysis.event.schemas import (
    CompanyCatalystsResult,
    EventAggregateResult,
    EventSignal,
    MacroSensitivityResult,
    ScheduledEventsResult,
)

__all__ = [
    "CompanyCatalystsResult",
    "EventAggregateResult",
    "EventSignal",
    "MacroSensitivityResult",
    "ScheduledEventsResult",
    "aggregate_event_signals",
    "analyze_company_catalysts",
    "analyze_event_aggregate",
    "analyze_event_inputs",
    "analyze_event_module",
    "analyze_macro_sensitivity",
    "analyze_scheduled_events",
]

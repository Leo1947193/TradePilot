from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import CompanyEvent, MacroCalendarEvent


POSITIVE_EVENT_TYPES = ("approval", "launch", "partnership", "merger", "acquisition")
RISK_EVENT_TYPES = ("earnings", "lawsuit", "recall", "regulatory", "fda")


@dataclass(frozen=True)
class EventSignal:
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


def analyze_event_inputs(
    company_events: list[CompanyEvent],
    macro_events: list[MacroCalendarEvent],
    *,
    analysis_time: datetime,
) -> EventSignal:
    near_term_company_risks = 0
    positive_catalysts = 0
    for event in company_events:
        days_until = (event.scheduled_at - analysis_time).total_seconds() / 86400
        event_type = event.event_type.lower()
        if 0 <= days_until <= 14 and any(term in event_type for term in RISK_EVENT_TYPES):
            near_term_company_risks += 1
        if any(term in event_type for term in POSITIVE_EVENT_TYPES):
            positive_catalysts += 1

    near_term_macro_risks = 0
    for event in macro_events:
        days_until = (event.scheduled_at - analysis_time).total_seconds() / 86400
        if 0 <= days_until <= 7 and (event.importance or "").lower() == "high":
            near_term_macro_risks += 1

    risk_score = near_term_company_risks + near_term_macro_risks
    total_events = len(company_events) + len(macro_events)

    if risk_score > positive_catalysts and risk_score > 0:
        direction = AnalysisDirection.BEARISH
        bias_label = "bearish"
    elif positive_catalysts > risk_score:
        direction = AnalysisDirection.BULLISH
        bias_label = "bullish"
    else:
        direction = AnalysisDirection.NEUTRAL
        bias_label = "neutral"

    low_confidence = total_events == 0
    data_completeness_pct = 100.0
    summary = (
        f"Event analysis found {len(company_events)} company events and {len(macro_events)} macro events "
        f"within the holding window. Near-term risks: {risk_score}; positive catalysts: "
        f"{positive_catalysts}; resulting bias: {bias_label}."
    )

    return EventSignal(
        direction=direction,
        summary=summary,
        data_completeness_pct=data_completeness_pct,
        low_confidence=low_confidence,
    )

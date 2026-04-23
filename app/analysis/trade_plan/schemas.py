from __future__ import annotations

from dataclasses import dataclass

from app.schemas.api import DecisionSynthesis, TradePlan


@dataclass(frozen=True)
class TradePlanInput:
    decision: DecisionSynthesis
    technical_report: dict | None = None
    event_report: dict | None = None


@dataclass(frozen=True)
class TradePlanSignal:
    trade_plan: TradePlan

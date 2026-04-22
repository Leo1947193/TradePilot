from __future__ import annotations

from dataclasses import dataclass

from app.schemas.api import DecisionSynthesis, TradePlan


@dataclass(frozen=True)
class TradePlanInput:
    decision: DecisionSynthesis


@dataclass(frozen=True)
class TradePlanSignal:
    trade_plan: TradePlan

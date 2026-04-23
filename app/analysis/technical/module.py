from __future__ import annotations

from collections import defaultdict

from app.analysis.technical.aggregate import aggregate_technical_signals, analyze_market_bars
from app.analysis.technical.momentum import analyze_momentum
from app.analysis.technical.multi_timeframe import analyze_multi_timeframe
from app.analysis.technical.patterns import analyze_patterns
from app.analysis.technical.risk_metrics import analyze_risk_metrics
from app.analysis.technical.schemas import TechnicalAggregateResult, TechnicalSubmoduleBundle
from app.analysis.technical.volume_price import analyze_volume_price
from app.schemas.modules import (
    AnalysisModuleName,
    AnalysisModuleResult,
    ModuleExecutionStatus,
)
from app.services.providers.dtos import MarketBar

MIN_RICH_TECHNICAL_BARS = 20


def analyze_technical_module(bars: list[MarketBar]) -> AnalysisModuleResult:
    aggregate_result = analyze_technical_aggregate(bars)
    return AnalysisModuleResult(
        module=AnalysisModuleName.TECHNICAL,
        status=ModuleExecutionStatus.USABLE,
        summary=aggregate_result.summary,
        direction=aggregate_result.technical_signal,
        data_completeness_pct=aggregate_result.data_completeness_pct,
        low_confidence=aggregate_result.low_confidence,
        reason=None,
    )


def analyze_technical_aggregate(bars: list[MarketBar]) -> TechnicalAggregateResult:
    daily_signal = analyze_market_bars(bars)
    if len(bars) < MIN_RICH_TECHNICAL_BARS:
        return aggregate_technical_signals(daily_signal=daily_signal)

    try:
        weekly_bars = _build_weekly_bars(bars)
        multi_timeframe_result = analyze_multi_timeframe(bars, weekly_bars)
        momentum_result = analyze_momentum(bars, [], benchmark_symbol=None)
        volume_price_result = analyze_volume_price(
            bars,
            key_support=multi_timeframe_result.key_support,
            key_resistance=multi_timeframe_result.key_resistance,
        )
        risk_metrics_result = analyze_risk_metrics(bars)
        patterns_result = analyze_patterns(
            bars,
            multi_timeframe_result=multi_timeframe_result,
            momentum_result=momentum_result,
            volume_price_result=volume_price_result,
            atr_14=risk_metrics_result.atr_14,
        )
    except ValueError:
        return aggregate_technical_signals(daily_signal=daily_signal)

    return aggregate_technical_signals(
        daily_signal=daily_signal,
        submodules=TechnicalSubmoduleBundle(
            multi_timeframe=multi_timeframe_result,
            momentum=momentum_result,
            volume_price=volume_price_result,
            risk_metrics=risk_metrics_result,
            patterns=patterns_result,
        ),
    )


def _build_weekly_bars(bars: list[MarketBar]) -> list[MarketBar]:
    grouped: dict[tuple[int, int], list[MarketBar]] = defaultdict(list)
    for bar in bars:
        iso_year, iso_week, _ = bar.timestamp.isocalendar()
        grouped[(iso_year, iso_week)].append(bar)

    weekly_bars: list[MarketBar] = []
    for _, week_bars in sorted(grouped.items()):
        first_bar = week_bars[0]
        last_bar = week_bars[-1]
        weekly_bars.append(
            MarketBar(
                symbol=first_bar.symbol,
                timestamp=last_bar.timestamp,
                open=first_bar.open,
                high=max(bar.high for bar in week_bars),
                low=min(bar.low for bar in week_bars),
                close=last_bar.close,
                volume=sum(bar.volume for bar in week_bars),
                source=last_bar.source,
            )
        )

    return weekly_bars

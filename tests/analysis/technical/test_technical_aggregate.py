from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.technical.momentum import MomentumResult
from app.analysis.technical.multi_timeframe import MultiTimeframeResult
from app.analysis.technical.patterns import PatternRecognitionResult
from app.analysis.technical.risk_metrics import RiskMetricsResult
from app.analysis.technical.aggregate import aggregate_technical_signals, analyze_market_bars
from app.analysis.technical.schemas import TechnicalSubmoduleBundle
from app.analysis.technical.volume_price import VolumePriceResult
from app.schemas.api import TechnicalSetupState
from app.schemas.modules import AnalysisDirection
from app.services.providers.dtos import MarketBar, ProviderSourceRef


def make_market_bar(
    *,
    day: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        symbol="AAPL",
        timestamp=datetime(2026, 4, day, 12, 0, tzinfo=UTC),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000000,
        source=ProviderSourceRef(
            name="yfinance",
            url="https://finance.yahoo.com/quote/AAPL/history",
            fetched_at=datetime(2026, 4, 17, 12, 5, tzinfo=UTC),
        ),
    )


def test_analyze_market_bars_preserves_existing_bullish_daily_behavior() -> None:
    signal = analyze_market_bars(
        [
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    assert signal.direction == AnalysisDirection.BULLISH
    assert signal.summary == (
        "Technical analysis reviewed 3 market bars. Price return over lookback: +3.17%. "
        "Latest close is above the short moving average, producing a bullish bias."
    )
    assert signal.data_completeness_pct == 5.0
    assert signal.low_confidence is False


def test_aggregate_technical_signals_keeps_daily_signal_as_module_anchor() -> None:
    daily_signal = analyze_market_bars(
        [
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    aggregate = aggregate_technical_signals(daily_signal=daily_signal)

    assert aggregate.technical_signal == AnalysisDirection.BULLISH
    assert aggregate.trend == AnalysisDirection.BULLISH
    assert aggregate.setup_state == TechnicalSetupState.ACTIONABLE
    assert aggregate.summary == daily_signal.summary
    assert aggregate.data_completeness_pct == 5.0
    assert aggregate.low_confidence is False
    assert aggregate.risk_flags == []
    assert aggregate.subsignals == {"daily_bars": daily_signal}


def test_aggregate_technical_signals_marks_neutral_low_confidence_as_watch() -> None:
    daily_signal = analyze_market_bars(
        [
            make_market_bar(day=15, open_price=188.0, high=189.0, low=187.0, close=188.0),
            make_market_bar(day=16, open_price=188.0, high=189.0, low=187.0, close=188.0),
            make_market_bar(day=17, open_price=188.0, high=189.0, low=187.0, close=188.0),
        ]
    )

    aggregate = aggregate_technical_signals(daily_signal=daily_signal)

    assert aggregate.technical_signal == AnalysisDirection.NEUTRAL
    assert aggregate.setup_state == TechnicalSetupState.WATCH
    assert aggregate.low_confidence is True
    assert aggregate.risk_flags == ["low_confidence", "neutral_signal"]


def test_aggregate_technical_signals_maps_richer_submodules_into_internal_contract() -> None:
    daily_signal = analyze_market_bars(
        [
            make_market_bar(day=15, open_price=188.0, high=190.0, low=187.0, close=189.0),
            make_market_bar(day=16, open_price=190.0, high=193.0, low=189.0, close=192.0),
            make_market_bar(day=17, open_price=192.0, high=196.0, low=191.0, close=195.0),
        ]
    )

    aggregate = aggregate_technical_signals(
        daily_signal=daily_signal,
        submodules=TechnicalSubmoduleBundle(
            multi_timeframe=MultiTimeframeResult(
                trend_daily="bullish",
                trend_weekly="bullish",
                ma_alignment="fully_bullish",
                key_support=[191.5, 188.0],
                key_resistance=[198.0, 202.5],
                data_completeness_pct=82.0,
                low_confidence=False,
                warnings=[],
            ),
            momentum=MomentumResult(
                rsi=63.4,
                rsi_signal="healthy",
                macd_signal="bullish_cross",
                adx=29.2,
                adx_trend_strength="strong",
                benchmark_used=None,
                relative_strength=1.14,
                momentum_summary="Momentum remains constructive.",
                data_completeness_pct=75.0,
                low_confidence=False,
                warnings=[],
            ),
            volume_price=VolumePriceResult(
                obv_trend="rising",
                obv_divergence="bullish",
                breakout_confirmed=True,
                breakdown_confirmed=False,
                volume_pattern="accumulation",
                data_completeness_pct=88.0,
                low_confidence=False,
            ),
            risk_metrics=RiskMetricsResult(
                atr_14=2.4,
                atr_pct=1.2,
                beta=None,
                bb_width=0.04,
                bb_squeeze=False,
                max_drawdown_63d=-0.08,
                iv_vs_hv=None,
                risk_flags=(),
                data_completeness_pct=66.67,
                low_confidence=False,
            ),
            patterns=PatternRecognitionResult(
                pattern_direction="bullish",
                pattern_detected="vcp",
                pattern_quality="high",
                entry_trigger=196.5,
                target_price=208.0,
                stop_loss_price=191.0,
                risk_reward_ratio=2.3,
                data_completeness_pct=90.0,
                low_confidence=False,
            ),
        ),
    )

    assert aggregate.technical_signal == AnalysisDirection.BULLISH
    assert aggregate.trend == AnalysisDirection.BULLISH
    assert aggregate.setup_state == TechnicalSetupState.ACTIONABLE
    assert aggregate.key_support == [191.5, 188.0]
    assert aggregate.key_resistance == [198.0, 202.5]
    assert aggregate.volume_pattern == "accumulation"
    assert aggregate.entry_trigger == "Watch for a move above 196.50 to confirm vcp."
    assert aggregate.target_price == 208.0
    assert aggregate.stop_loss_price == 191.0
    assert aggregate.risk_reward_ratio == 2.3
    assert aggregate.low_confidence is False
    assert aggregate.risk_flags == []
    assert set(aggregate.subsignals) == {
        "daily_bars",
        "multi_timeframe",
        "momentum",
        "volume_price",
        "patterns",
        "risk_metrics",
    }

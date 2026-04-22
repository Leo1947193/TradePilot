from __future__ import annotations

import json

from app.analysis.sentiment.schemas import (
    ExpectationShiftResult,
    NarrativeCrowdingResult,
    NewsToneResult,
    NormalizedSentimentDataset,
    SentimentAggregateResult,
)
from app.schemas.modules import AnalysisDirection

CONFIGURED_WEIGHTS = {
    "news": 0.40,
    "expectation": 0.35,
    "narrative": 0.25,
}


def aggregate_sentiment_signals(
    *,
    dataset: NormalizedSentimentDataset,
    news_tone: NewsToneResult,
    expectation_shift: ExpectationShiftResult,
    narrative_crowding: NarrativeCrowdingResult,
) -> SentimentAggregateResult:
    applied_weights = {
        "news": CONFIGURED_WEIGHTS["news"],
        "expectation": CONFIGURED_WEIGHTS["expectation"],
        "narrative": CONFIGURED_WEIGHTS["narrative"],
    }
    composite_score = round(
        _clamp(news_tone.recency_weighted_score) * applied_weights["news"]
        + _clamp(expectation_shift.expectation_score) * applied_weights["expectation"]
        + _direction_value(narrative_crowding.direction) * applied_weights["narrative"],
        2,
    )
    sentiment_bias = _resolve_sentiment_bias(
        composite_score=composite_score,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
    )
    key_risks = _build_key_risks(
        dataset=dataset,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )
    low_confidence_modules = _build_low_confidence_modules(
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )
    summary = _build_integrated_summary(
        sentiment_bias=sentiment_bias,
        news_tone=news_tone,
        expectation_shift=expectation_shift,
        narrative_crowding=narrative_crowding,
    )
    market_expectation = _build_market_expectation(
        sentiment_bias=sentiment_bias,
        expectation_shift=expectation_shift,
        key_risks=key_risks,
    )
    weight_scheme_used = json.dumps(
        {
            "configured_weights": CONFIGURED_WEIGHTS,
            "available_weight_sum": 1.0,
            "applied_weights": applied_weights,
            "renormalized": False,
            "scheme": "sentiment_signal_aggregation_v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    return SentimentAggregateResult(
        sentiment_bias=sentiment_bias,
        composite_score=composite_score,
        news_tone=news_tone.news_tone,
        market_expectation=market_expectation,
        key_risks=key_risks,
        data_completeness_pct=news_tone.data_completeness_pct,
        low_confidence=bool(low_confidence_modules),
        low_confidence_modules=low_confidence_modules,
        weight_scheme_used=weight_scheme_used,
        subresults={
            "normalized_news": dataset,
            "news_tone": news_tone,
            "expectation_shift": expectation_shift,
            "narrative_crowding": narrative_crowding,
        },
        summary=summary,
    )


def _resolve_sentiment_bias(
    *,
    composite_score: float,
    news_tone: NewsToneResult,
    expectation_shift: ExpectationShiftResult,
) -> AnalysisDirection:
    if (
        abs(composite_score) < 0.2
        and expectation_shift.direction not in {AnalysisDirection.NEUTRAL, news_tone.direction}
    ):
        return AnalysisDirection.NEUTRAL
    if composite_score >= 0.2:
        return AnalysisDirection.BULLISH
    if composite_score <= -0.2:
        return AnalysisDirection.BEARISH
    return news_tone.direction


def _build_key_risks(
    *,
    dataset: NormalizedSentimentDataset,
    news_tone: NewsToneResult,
    expectation_shift: ExpectationShiftResult,
    narrative_crowding: NarrativeCrowdingResult,
) -> list[str]:
    risks: list[str] = []
    if dataset.deduped_article_count < 2:
        risks.append("limited_news_coverage")
    if expectation_shift.low_confidence:
        risks.append("expectation_shift_low_confidence")
    if narrative_crowding.low_confidence:
        risks.append("narrative_low_confidence")
    if narrative_crowding.crowding_flag:
        risks.append("crowded_narrative")
    if expectation_shift.direction != news_tone.direction and expectation_shift.direction != AnalysisDirection.NEUTRAL:
        risks.append("cross_signal_conflict")
    return risks


def _build_low_confidence_modules(
    *,
    news_tone: NewsToneResult,
    expectation_shift: ExpectationShiftResult,
    narrative_crowding: NarrativeCrowdingResult,
) -> list[str]:
    modules: list[str] = []
    if news_tone.low_confidence:
        modules.append("news_tone")
    if expectation_shift.low_confidence:
        modules.append("expectation_shift")
    if narrative_crowding.low_confidence:
        modules.append("narrative_crowding")
    return modules


def _build_integrated_summary(
    *,
    sentiment_bias: AnalysisDirection,
    news_tone: NewsToneResult,
    expectation_shift: ExpectationShiftResult,
    narrative_crowding: NarrativeCrowdingResult,
) -> str:
    return (
        f"Sentiment bias is {sentiment_bias.value}; news tone is {news_tone.news_tone}, "
        f"expectation shift is {expectation_shift.expectation_shift.lower()}, "
        f"and narrative state is {narrative_crowding.narrative_state.lower()}."
    )


def _build_market_expectation(
    *,
    sentiment_bias: AnalysisDirection,
    expectation_shift: ExpectationShiftResult,
    key_risks: list[str],
) -> str:
    if sentiment_bias == AnalysisDirection.BULLISH:
        message = f"Expectations are constructive with {expectation_shift.expectation_shift.lower()} signals."
    elif sentiment_bias == AnalysisDirection.BEARISH:
        message = f"Expectations are cautious with {expectation_shift.expectation_shift.lower()} signals."
    else:
        message = "Expectations are balanced without a strong directional edge."

    if key_risks:
        return f"{message} Key risk: {key_risks[0].replace('_', ' ')}."
    return message


def _direction_value(direction: AnalysisDirection) -> int:
    if direction == AnalysisDirection.BULLISH:
        return 1
    if direction == AnalysisDirection.BEARISH:
        return -1
    return 0


def _clamp(score: float) -> float:
    return max(-1.0, min(1.0, score))

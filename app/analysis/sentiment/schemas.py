from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AnyUrl, ConfigDict

from app.schemas.modules import AnalysisDirection, ModuleSchema


class SourceTraceEntry(ModuleSchema):
    dataset: str
    source: str
    source_url: AnyUrl | None = None
    article_url: AnyUrl | None = None
    fetched_at: datetime
    missing_fields: tuple[str, ...] = ()


class NormalizedNewsItem(ModuleSchema):
    symbol: str
    title: str
    canonical_headline: str
    normalized_headline: str
    combined_text: str
    published_at: datetime
    source_name: str
    source_url: AnyUrl
    category: str | None = None
    dedupe_cluster_id: str
    cluster_size: int = 1
    is_relevant: bool
    relevance_score: float
    relevance_label: str
    classifier_version: str
    source_trace: tuple[SourceTraceEntry, ...]


class NormalizedSentimentDataset(ModuleSchema):
    ticker: str
    provider_article_count: int
    relevant_article_count: int
    deduped_article_count: int
    excluded_article_count: int
    items: tuple[NormalizedNewsItem, ...]


class SentimentSignal(ModuleSchema):
    direction: AnalysisDirection
    summary: str
    data_completeness_pct: float
    low_confidence: bool


class NewsToneResult(ModuleSchema):
    direction: AnalysisDirection
    news_tone: str
    bullish_hits: int
    bearish_hits: int
    recency_weighted_score: float
    summary: str
    data_completeness_pct: float
    low_confidence: bool
    source_trace: tuple[SourceTraceEntry, ...]
    classifier_version: str


class ExpectationShiftResult(ModuleSchema):
    direction: AnalysisDirection
    expectation_shift: str
    expectation_score: float
    summary: str
    data_completeness_pct: float
    low_confidence: bool


class NarrativeCrowdingResult(ModuleSchema):
    direction: AnalysisDirection
    narrative_state: str
    dominant_narrative: str
    contradiction_ratio: float
    attention_zscore_7d: float
    crowding_flag: bool
    summary: str
    data_completeness_pct: float
    low_confidence: bool


class SentimentAggregateResult(ModuleSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sentiment_bias: AnalysisDirection
    composite_score: float
    news_tone: str
    market_expectation: str
    key_risks: list[str]
    data_completeness_pct: float
    low_confidence: bool
    low_confidence_modules: list[str]
    weight_scheme_used: str
    subresults: dict[str, Any]
    summary: str

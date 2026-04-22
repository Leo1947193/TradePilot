from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.analysis.sentiment.narrative_crowding import analyze_narrative_crowding


def test_analyze_narrative_crowding_detects_supportive_crowded_theme() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    mention_series = []
    for offset in range(96, 7, -1):
        mention_series.append(
            {
                "date": (analysis_time - timedelta(days=offset)).date(),
                "mention_count": 1,
                "unique_source_count": 1,
            }
        )
    for offset in range(6, -1, -1):
        mention_series.append(
            {
                "date": (analysis_time - timedelta(days=offset)).date(),
                "mention_count": 5,
                "unique_source_count": 3,
            }
        )

    result = analyze_narrative_crowding(
        {
            "analysis_time": analysis_time,
            "normalized_news_items": [
                {
                    "headline": "Demand growth stays strong on rising orders",
                    "published_at": datetime(2026, 4, 22, 8, 0, tzinfo=UTC),
                    "source_name": "Source A",
                    "url": "https://example.com/a1",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "Inventory clears as demand improves again",
                    "published_at": datetime(2026, 4, 21, 8, 0, tzinfo=UTC),
                    "source_name": "Source B",
                    "url": "https://example.com/a2",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "New launch execution stays strong for demand cycle",
                    "published_at": datetime(2026, 4, 20, 8, 0, tzinfo=UTC),
                    "source_name": "Source C",
                    "url": "https://example.com/a3",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "Orders remain strong as production ramps",
                    "published_at": datetime(2026, 4, 19, 8, 0, tzinfo=UTC),
                    "source_name": "Source A",
                    "url": "https://example.com/a4",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "Demand growth remains strong across channels",
                    "published_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
                    "source_name": "Source B",
                    "url": "https://example.com/a5",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "Product delivery improves as orders accelerate",
                    "published_at": datetime(2026, 4, 17, 8, 0, tzinfo=UTC),
                    "source_name": "Source C",
                    "url": "https://example.com/a6",
                    "relevance_score": 0.9,
                },
            ],
            "mention_series": mention_series,
        }
    )

    assert result.direction == "bullish"
    assert result.narrative_state == "supportive"
    assert result.dominant_narrative.startswith("demand_cycle")
    assert result.contradiction_ratio == 0.0
    assert result.attention_zscore_7d > 2.0
    assert result.crowding_flag is True
    assert result.low_confidence is False


def test_analyze_narrative_crowding_falls_back_when_attention_baseline_is_short() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = analyze_narrative_crowding(
        {
            "analysis_time": analysis_time,
            "normalized_news_items": [
                {
                    "headline": "Demand growth stays strong",
                    "published_at": datetime(2026, 4, 22, 8, 0, tzinfo=UTC),
                    "source_name": "Source A",
                    "url": "https://example.com/b1",
                    "relevance_score": 0.9,
                },
                {
                    "headline": "Margins face pressure after product delay",
                    "published_at": datetime(2026, 4, 21, 8, 0, tzinfo=UTC),
                    "source_name": "Source B",
                    "url": "https://example.com/b2",
                    "relevance_score": 0.9,
                },
            ],
            "mention_series": [
                {
                    "date": date(2026, 4, 21),
                    "mention_count": 2,
                    "unique_source_count": 2,
                },
                {
                    "date": date(2026, 4, 22),
                    "mention_count": 2,
                    "unique_source_count": 2,
                },
            ],
        }
    )

    assert result.direction == "neutral"
    assert result.narrative_state == "mixed"
    assert result.attention_zscore_7d == 0.0
    assert result.crowding_flag is False
    assert result.low_confidence is True
    assert "attention baseline fallback applied" in result.summary

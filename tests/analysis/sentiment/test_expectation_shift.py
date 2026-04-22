from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.sentiment.expectation_shift import analyze_expectation_shift


def test_analyze_expectation_shift_dedupes_actions_and_uses_latest_target_revision() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = analyze_expectation_shift(
        {
            "analysis_time": analysis_time,
            "analyst_actions": [
                {
                    "action_id": "dup-upgrade",
                    "published_at": datetime(2026, 4, 20, 13, 0, tzinfo=UTC),
                    "analyst_firm": "Firm A",
                    "rating_action": "upgrade",
                    "target_price_old": 100,
                    "target_price_new": 130,
                    "currency": "USD",
                    "fetched_at": datetime(2026, 4, 20, 13, 15, tzinfo=UTC),
                },
                {
                    "action_id": "dup-upgrade",
                    "published_at": datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                    "analyst_firm": "Firm A",
                    "rating_action": "upgrade",
                    "target_price_old": 100,
                    "currency": "USD",
                    "fetched_at": datetime(2026, 4, 20, 12, 5, tzinfo=UTC),
                },
                {
                    "action_id": "downgrade-1",
                    "published_at": datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
                    "analyst_firm": "Firm B",
                    "rating_action": "downgrade",
                    "target_price_old": 90,
                    "target_price_new": 81,
                    "currency": "USD",
                    "fetched_at": datetime(2026, 4, 18, 12, 5, tzinfo=UTC),
                },
            ],
            "expectation_proxy_events": [
                {
                    "event_id": "proxy-positive",
                    "published_at": datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
                    "headline": "Company raises guidance",
                    "tag": "guidance_raise",
                    "relevance_score": 0.9,
                    "url": "https://example.com/proxy-positive",
                    "classifier_version": "v2",
                    "fetched_at": datetime(2026, 4, 21, 9, 5, tzinfo=UTC),
                },
                {
                    "event_id": "proxy-negative",
                    "published_at": datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                    "headline": "Demand softening",
                    "tag": "demand_softening",
                    "relevance_score": 0.8,
                    "url": "https://example.com/proxy-negative",
                    "classifier_version": "v1",
                    "fetched_at": datetime(2026, 4, 20, 9, 5, tzinfo=UTC),
                },
                {
                    "event_id": "proxy-positive-2",
                    "published_at": datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
                    "headline": "Execution improving",
                    "tag": "execution_improving",
                    "relevance_score": 0.7,
                    "url": "https://example.com/proxy-positive-2",
                    "classifier_version": "v1",
                    "fetched_at": datetime(2026, 4, 19, 9, 5, tzinfo=UTC),
                },
            ],
        }
    )

    assert result.direction == "bullish"
    assert result.expectation_shift == "improving"
    assert result.expectation_score == 60.77
    assert result.data_completeness_pct == 62.5
    assert result.low_confidence is False
    assert "analyst balance 0.00" in result.summary
    assert "target revision median 10.00%" in result.summary
    assert "expectation headline balance 0.33" in result.summary


def test_analyze_expectation_shift_marks_sparse_inputs_low_confidence() -> None:
    analysis_time = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = analyze_expectation_shift(
        {
            "analysis_time": analysis_time,
            "analyst_actions": [
                {
                    "action_id": "single",
                    "published_at": datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
                    "analyst_firm": "Firm A",
                    "rating_action": "downgrade",
                    "fetched_at": datetime(2026, 4, 21, 12, 5, tzinfo=UTC),
                }
            ],
            "expectation_proxy_events": [
                {
                    "event_id": "single-proxy",
                    "published_at": datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
                    "headline": "Guidance cut",
                    "tag": "guidance_cut",
                    "relevance_score": 0.9,
                    "url": "https://example.com/guidance-cut",
                    "classifier_version": "v1",
                    "fetched_at": datetime(2026, 4, 21, 9, 5, tzinfo=UTC),
                }
            ],
        }
    )

    assert result.direction == "bearish"
    assert result.expectation_shift == "deteriorating"
    assert result.low_confidence is True
    assert result.data_completeness_pct == 25.0
    assert "attention Low" in result.summary

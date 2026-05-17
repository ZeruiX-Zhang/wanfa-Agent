"""Unit test for the structured ``ExperimentReview`` dataclass (Task 4.9).

Covers Requirement 9.1: the review carries structured key metrics and a
derived ``metric_breach`` predicate, and round-trips through ``to_dict``
/ ``from_dict`` without loss.
"""

from __future__ import annotations

from apps.api.app.reality_layers import ExperimentReview, KeyMetric


def test_dataclass_round_trip_with_metrics() -> None:
    """An ExperimentReview survives a to_dict/from_dict round trip."""

    review = ExperimentReview(
        id="exr_1",
        tenant_id="tnt_x",
        experiment_id="exp_1",
        result_class="partial",
        key_metrics=[
            KeyMetric(name="latency_ms", target=100.0, value=104.0, tolerance=10.0),
            KeyMetric(name="error_rate", target=0.01, value=0.05, tolerance=0.01),
        ],
        notes="mostly worked",
        created_at="2026-03-01T00:00:00+00:00",
    )

    # latency within tolerance, error_rate breached -> overall breach True.
    assert review.key_metrics[0].breached is False
    assert review.key_metrics[1].breached is True
    assert review.metric_breach is True

    restored = ExperimentReview.from_dict(review.to_dict())

    assert restored.id == review.id
    assert restored.tenant_id == review.tenant_id
    assert restored.experiment_id == review.experiment_id
    assert restored.result_class == review.result_class
    assert restored.notes == review.notes
    assert restored.created_at == review.created_at
    assert restored.metric_breach is True
    assert len(restored.key_metrics) == 2
    assert restored.key_metrics[0].name == "latency_ms"
    assert restored.key_metrics[0].value == 104.0
    assert restored.key_metrics[1].breached is True


def test_no_metrics_means_no_breach() -> None:
    """A review with no key metrics never reports a breach."""

    review = ExperimentReview(
        id="exr_2",
        tenant_id="tnt_x",
        experiment_id="exp_2",
        result_class="success",
        key_metrics=[],
        notes="",
        created_at="2026-03-02T00:00:00+00:00",
    )
    assert review.metric_breach is False
    assert ExperimentReview.from_dict(review.to_dict()).metric_breach is False

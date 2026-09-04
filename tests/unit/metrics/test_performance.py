from datetime import datetime, timezone

import pytest

from driftwatch.metrics.performance import compute_performance
from driftwatch.store.base import EventRecord


def _event(request_id: str, output) -> EventRecord:
    return EventRecord(
        event_id=request_id,
        session_id="s1",
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        status="ok",
        input={},
        output=output,
    )


def test_label_coverage_zero_with_no_labels():
    events = [_event("r1", 1), _event("r2", 0)]
    results = compute_performance(events, labels={})
    coverage = next(r for r in results if r.metric_name == "label_coverage")
    assert coverage.value == 0.0
    assert len(results) == 1  # nothing else computable without matched labels


def test_classification_metrics_perfect_predictions():
    events = [_event(f"r{i}", i % 2) for i in range(10)]
    labels = {f"r{i}": i % 2 for i in range(10)}
    results = compute_performance(events, labels, task_type="classification")

    coverage = next(r for r in results if r.metric_name == "label_coverage")
    accuracy = next(r for r in results if r.metric_name == "accuracy")
    f1 = next(r for r in results if r.metric_name == "f1")
    assert coverage.value == 1.0
    assert accuracy.value == 1.0
    assert f1.value == 1.0


def test_classification_metrics_partial_coverage_and_errors():
    events = [_event("r1", 1), _event("r2", 0), _event("r3", 1)]
    labels = {"r1": 1, "r2": 1}  # r3 has no label yet; r2 was mispredicted
    results = compute_performance(events, labels, task_type="classification")

    coverage = next(r for r in results if r.metric_name == "label_coverage")
    accuracy = next(r for r in results if r.metric_name == "accuracy")
    assert coverage.value == pytest.approx(2 / 3)
    assert accuracy.value == 0.5


def test_regression_metrics():
    events = [_event(f"r{i}", float(i)) for i in range(5)]
    labels = {f"r{i}": float(i) + 1.0 for i in range(5)}  # constant offset of 1.0
    results = compute_performance(events, labels, task_type="regression")

    mae = next(r for r in results if r.metric_name == "mae")
    rmse = next(r for r in results if r.metric_name == "rmse")
    assert mae.value == 1.0
    assert rmse.value == 1.0


def test_infers_classification_for_low_cardinality_int_labels():
    events = [_event(f"r{i}", i % 2) for i in range(20)]
    labels = {f"r{i}": i % 2 for i in range(20)}
    results = compute_performance(events, labels)  # no task_type passed
    assert any(r.metric_name == "accuracy" for r in results)


def test_infers_regression_for_continuous_labels():
    events = [_event(f"r{i}", float(i) * 1.1) for i in range(20)]
    labels = {f"r{i}": float(i) * 1.1 for i in range(20)}
    results = compute_performance(events, labels)  # no task_type passed
    assert any(r.metric_name == "mae" for r in results)

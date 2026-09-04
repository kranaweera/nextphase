"""Buckets events into closed time windows and computes drift, quality, and
performance metrics per window.

A window is only computed once it has fully elapsed, and already-computed
(window, metric, feature) combinations are skipped per category, so this is
safe to call repeatedly (e.g. from the alerting scheduler in M8) without
recomputing or duplicating metric rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from driftwatch.metrics.performance import TaskType, compute_performance
from driftwatch.metrics.quality import compute_tabular_quality, compute_text_quality
from driftwatch.profilers.base import DriftResult, Profiler
from driftwatch.store.base import (
    AbstractStore,
    EventRecord,
    MetricCategory,
    MetricValueRecord,
)

_WINDOW_SECONDS = {"1h": 3600, "1d": 86400}


def _floor_to_window(ts: datetime, window: str) -> datetime:
    seconds = _WINDOW_SECONDS[window]
    epoch = ts.timestamp()
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def _to_metric_records(
    session_id: str,
    category: MetricCategory,
    window_start: datetime,
    window_end: datetime,
    results: list[DriftResult],
    existing_keys: set[tuple[datetime, str, str | None]],
    computed_at: datetime,
) -> list[MetricValueRecord]:
    records = []
    for r in results:
        key = (window_start, r.metric_name, r.feature_name)
        if key in existing_keys:
            continue
        details = dict(r.details or {})
        if r.is_drifted is not None:
            details["is_drifted"] = r.is_drifted
        records.append(
            MetricValueRecord(
                session_id=session_id,
                metric_category=category,
                metric_name=r.metric_name,
                feature_name=r.feature_name,
                window_start=window_start,
                window_end=window_end,
                value=r.value,
                details=details or None,
                computed_at=computed_at,
            )
        )
    return records


def compute_window_metrics(
    store: AbstractStore,
    session_id: str,
    profiler: Profiler,
    task_type: TaskType | None = None,
    window: str = "1h",
    now: datetime | None = None,
) -> list[MetricValueRecord]:
    """Compute + persist drift/quality/performance metrics for every
    fully-elapsed window missing them."""
    now = now or datetime.now(timezone.utc)
    baseline = store.get_baseline(session_id)
    if baseline is None:
        return []

    events = store.query_events(session_id, limit=100_000)
    if not events:
        return []

    window_seconds = _WINDOW_SECONDS[window]
    buckets: dict[datetime, list[EventRecord]] = {}
    for event in events:
        window_start = _floor_to_window(event.timestamp, window)
        if window_start + timedelta(seconds=window_seconds) > now:
            continue  # window hasn't fully elapsed yet
        buckets.setdefault(window_start, []).append(event)

    existing_by_category: dict[MetricCategory, set[tuple[datetime, str, str | None]]] = {
        category: {
            (m.window_start, m.metric_name, m.feature_name)
            for m in store.query_metrics(session_id, category=category)
        }
        for category in ("drift", "quality", "performance")
    }

    new_values: list[MetricValueRecord] = []
    for window_start, window_events in buckets.items():
        window_end = window_start + timedelta(seconds=window_seconds)
        window_features = [profiler.extract_features(e.input) for e in window_events]
        computed_at = datetime.now(timezone.utc)

        drift_results = profiler.compute_drift(baseline.summary_stats, window_features)
        new_values += _to_metric_records(
            session_id, "drift", window_start, window_end, drift_results,
            existing_by_category["drift"], computed_at,
        )

        if profiler.modality == "tabular":
            quality_results = compute_tabular_quality(baseline.summary_stats, window_features)
        elif profiler.modality == "text":
            quality_results = compute_text_quality(window_features)
        else:
            quality_results = []
        new_values += _to_metric_records(
            session_id, "quality", window_start, window_end, quality_results,
            existing_by_category["quality"], computed_at,
        )

        request_ids = [e.request_id for e in window_events]
        labels = store.get_labels(session_id, request_ids)
        performance_results = compute_performance(window_events, labels, task_type)
        new_values += _to_metric_records(
            session_id, "performance", window_start, window_end, performance_results,
            existing_by_category["performance"], computed_at,
        )

    if new_values:
        store.log_metric_values(new_values)
    return new_values

"""Buckets events into closed time windows and computes drift metrics per window.

A window is only computed once it has fully elapsed, and already-computed
(window, metric, feature) combinations are skipped, so this is safe to call
repeatedly (e.g. from the alerting scheduler in M8) without recomputing or
duplicating metric rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from driftwatch.profilers.base import Profiler
from driftwatch.store.base import AbstractStore, MetricValueRecord

_WINDOW_SECONDS = {"1h": 3600, "1d": 86400}


def _floor_to_window(ts: datetime, window: str) -> datetime:
    seconds = _WINDOW_SECONDS[window]
    epoch = ts.timestamp()
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def compute_drift_metrics(
    store: AbstractStore,
    session_id: str,
    profiler: Profiler,
    window: str = "1h",
    now: datetime | None = None,
) -> list[MetricValueRecord]:
    """Compute + persist drift metrics for every fully-elapsed window missing them."""
    now = now or datetime.now(timezone.utc)
    baseline = store.get_baseline(session_id)
    if baseline is None:
        return []

    events = store.query_events(session_id, limit=100_000)
    if not events:
        return []

    window_seconds = _WINDOW_SECONDS[window]
    buckets: dict[datetime, list] = {}
    for event in events:
        window_start = _floor_to_window(event.timestamp, window)
        if window_start + timedelta(seconds=window_seconds) > now:
            continue  # window hasn't fully elapsed yet
        buckets.setdefault(window_start, []).append(event)

    already_computed = {
        (m.window_start, m.metric_name, m.feature_name)
        for m in store.query_metrics(session_id, category="drift")
    }

    new_values: list[MetricValueRecord] = []
    for window_start, window_events in buckets.items():
        window_end = window_start + timedelta(seconds=window_seconds)
        window_features = [profiler.extract_features(e.input) for e in window_events]
        drift_results = profiler.compute_drift(baseline.summary_stats, window_features)
        computed_at = datetime.now(timezone.utc)

        for dr in drift_results:
            key = (window_start, dr.metric_name, dr.feature_name)
            if key in already_computed:
                continue
            details = dict(dr.details or {})
            if dr.is_drifted is not None:
                details["is_drifted"] = dr.is_drifted
            new_values.append(
                MetricValueRecord(
                    session_id=session_id,
                    metric_category="drift",
                    metric_name=dr.metric_name,
                    feature_name=dr.feature_name,
                    window_start=window_start,
                    window_end=window_end,
                    value=dr.value,
                    details=details or None,
                    computed_at=computed_at,
                )
            )

    if new_values:
        store.log_metric_values(new_values)
    return new_values

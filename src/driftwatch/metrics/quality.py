"""Data-quality checks, independent of whether the profiler detects drift.

Tabular: duplicate-row rate, out-of-range rate per numeric feature.
Text: empty-string rate, exact-duplicate rate.
(Missing-value rate and schema drift are already covered by
`TabularProfiler.compute_drift` and reported under the "drift" category.)
"""

from __future__ import annotations

from typing import Any

from driftwatch.profilers.base import DriftResult


def compute_tabular_quality(
    baseline_stats: dict[str, Any], window_features: list[dict[str, list[Any]]]
) -> list[DriftResult]:
    columns: dict[str, list[Any]] = {}
    for feats in window_features:
        for col, vals in feats.items():
            columns.setdefault(col, []).extend(vals)
    if not columns:
        return []

    col_names = sorted(columns)
    row_count = len(columns[col_names[0]])
    rows = list(zip(*(columns[c] for c in col_names), strict=True))
    duplicate_rate = 1 - (len(set(map(str, rows))) / row_count) if row_count else 0.0
    results = [DriftResult(metric_name="duplicate_rate", value=duplicate_rate)]

    for col, base in baseline_stats.get("columns", {}).items():
        if base.get("kind") != "numeric" or base.get("min") is None:
            continue
        vals = [v for v in columns.get(col, []) if isinstance(v, int | float)]
        if not vals:
            continue
        lo, hi = base["min"], base["max"]
        out_of_range_rate = sum(1 for v in vals if v < lo or v > hi) / len(vals)
        results.append(
            DriftResult(metric_name="out_of_range_rate", feature_name=col, value=out_of_range_rate)
        )

    return results


def compute_text_quality(window_features: list[dict[str, list[Any]]]) -> list[DriftResult]:
    texts: list[str] = []
    for feats in window_features:
        texts.extend(feats.get("text", []))
    if not texts:
        return []

    empty_rate = sum(1 for t in texts if not t.strip()) / len(texts)
    duplicate_rate = 1 - (len(set(texts)) / len(texts))
    return [
        DriftResult(metric_name="empty_rate", value=empty_rate),
        DriftResult(metric_name="duplicate_rate", value=duplicate_rate),
    ]

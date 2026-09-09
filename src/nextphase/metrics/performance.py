"""Delayed-label performance metrics.

Joins a window's events with whatever labels have been logged so far
(`Session.log_labels`) on `request_id`. Labels typically arrive late and
partially, so `label_coverage` (matched / total) is always emitted, even
when it's 0 — that's a meaningful signal on its own, not a missing value.
"""

from __future__ import annotations

from typing import Any, Literal

from nextphase.profilers.base import DriftResult
from nextphase.store.base import EventRecord

TaskType = Literal["classification", "regression"]


def _looks_like_probabilities(values: list[Any]) -> bool:
    return (
        all(isinstance(v, float) for v in values)
        and all(0.0 <= v <= 1.0 for v in values)
        and len(set(values)) > 2
    )


def _infer_task_type(y_true: list[Any]) -> TaskType:
    all_int_like = all(
        isinstance(v, bool) or isinstance(v, int) or (isinstance(v, float) and v.is_integer())
        for v in y_true
    )
    if all_int_like and len(set(y_true)) <= max(20, len(y_true) // 10):
        return "classification"
    return "regression"


def compute_performance(
    events: list[EventRecord],
    labels: dict[str, Any],
    task_type: TaskType | None = None,
) -> list[DriftResult]:
    matched = [(e, labels[e.request_id]) for e in events if e.request_id in labels]
    label_coverage = len(matched) / len(events) if events else 0.0
    results = [DriftResult(metric_name="label_coverage", value=label_coverage)]
    if not matched:
        return results

    y_pred = [e.output for e, _ in matched]
    y_true = [y for _, y in matched]
    resolved_task = task_type or _infer_task_type(y_true)

    if resolved_task == "classification":
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

        results += [
            DriftResult(metric_name="accuracy", value=float(accuracy_score(y_true, y_pred))),
            DriftResult(
                metric_name="precision",
                value=float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
            ),
            DriftResult(
                metric_name="recall",
                value=float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
            ),
            DriftResult(
                metric_name="f1",
                value=float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
            ),
        ]
        if len(set(y_true)) == 2 and _looks_like_probabilities(y_pred):
            from sklearn.metrics import roc_auc_score

            try:
                results.append(
                    DriftResult(metric_name="auc_roc", value=float(roc_auc_score(y_true, y_pred)))
                )
            except ValueError:
                pass  # e.g. only one class present in this window's matched labels
    else:
        from sklearn.metrics import mean_absolute_error, mean_squared_error

        results += [
            DriftResult(metric_name="mae", value=float(mean_absolute_error(y_true, y_pred))),
            DriftResult(
                metric_name="rmse", value=float(mean_squared_error(y_true, y_pred) ** 0.5)
            ),
        ]

    return results

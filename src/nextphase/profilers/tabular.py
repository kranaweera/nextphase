"""Tabular drift: PSI, KS-test, Wasserstein distance, missing-rate delta, schema drift."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
from scipy import stats as scipy_stats

from nextphase.profilers.base import DriftResult, Profiler

_PSI_EPSILON = 1e-4
_MAX_BASELINE_SAMPLE = 1000
_PSI_DRIFT_THRESHOLD = 0.2  # <0.1 stable, 0.1-0.2 moderate, >0.2 significant (industry convention)
_KS_P_VALUE_THRESHOLD = 0.05


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _bin_proportions(values: list[float], edges: list[float]) -> list[float]:
    if not values:
        return [0.0] * (len(edges) - 1)
    binned = pd.cut(pd.Series(values, dtype="float64"), bins=edges, include_lowest=True)
    counts = binned.value_counts(sort=False)
    total = counts.sum()
    return [0.0] * len(counts) if total == 0 else (counts / total).tolist()


def _psi(baseline_props: list[float], window_props: list[float]) -> float:
    psi = 0.0
    for b, w in zip(baseline_props, window_props, strict=True):
        b = max(b, _PSI_EPSILON)
        w = max(w, _PSI_EPSILON)
        psi += (w - b) * math.log(w / b)
    return psi


def _psi_categorical(baseline_dist: dict[str, float], window_values: list[Any]) -> float:
    window_dist = pd.Series([str(v) for v in window_values]).value_counts(normalize=True).to_dict()
    categories = set(baseline_dist) | set(window_dist)
    psi = 0.0
    for c in categories:
        b = max(baseline_dist.get(c, 0.0), _PSI_EPSILON)
        w = max(window_dist.get(c, 0.0), _PSI_EPSILON)
        psi += (w - b) * math.log(w / b)
    return psi


class TabularProfiler(Profiler):
    modality = "tabular"

    def extract_features(self, raw_input: Any) -> dict[str, list[Any]]:
        if hasattr(raw_input, "columns") and hasattr(raw_input, "to_dict"):  # DataFrame
            return {col: raw_input[col].tolist() for col in raw_input.columns}
        if isinstance(raw_input, dict):
            return {k: [v] for k, v in raw_input.items()}
        if isinstance(raw_input, list) and all(isinstance(row, dict) for row in raw_input):
            # A DataFrame that round-tripped through JSON storage becomes list[dict]
            # (one dict per row, via pandas .to_dict(orient="records")).
            cols: dict[str, list[Any]] = {}
            for row in raw_input:
                for k, v in row.items():
                    cols.setdefault(k, []).append(v)
            return cols
        raise TypeError(f"TabularProfiler can't extract features from {type(raw_input)!r}")

    def compute_baseline_stats(self, reference_data: pd.DataFrame) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        for col in reference_data.columns:
            series = reference_data[col]
            null_rate = float(series.isna().mean())
            clean = series.dropna()

            if pd.api.types.is_numeric_dtype(series):
                quantiles = [i / 10 for i in range(11)]
                raw_edges = clean.quantile(quantiles).tolist() if len(clean) else []
                edges = sorted(set(raw_edges)) if raw_edges else [0.0, 1.0]
                if len(edges) < 2:
                    edges = [edges[0] - 0.5, edges[0] + 0.5] if edges else [0.0, 1.0]
                sample = (
                    clean.sample(min(len(clean), _MAX_BASELINE_SAMPLE), random_state=0).tolist()
                    if len(clean)
                    else []
                )
                columns[col] = {
                    "kind": "numeric",
                    "mean": float(clean.mean()) if len(clean) else None,
                    "std": float(clean.std()) if len(clean) else None,
                    "min": float(clean.min()) if len(clean) else None,
                    "max": float(clean.max()) if len(clean) else None,
                    "bin_edges": edges,
                    "bin_proportions": _bin_proportions(clean.tolist(), edges),
                    "values_sample": sample,
                    "null_rate": null_rate,
                }
            else:
                columns[col] = {
                    "kind": "categorical",
                    "distribution": {
                        str(k): float(v)
                        for k, v in clean.value_counts(normalize=True).to_dict().items()
                    },
                    "null_rate": null_rate,
                }
        return {"columns": columns, "row_count": len(reference_data)}

    def compute_drift(
        self, baseline_stats: dict[str, Any], window_features: list[dict[str, Any]]
    ) -> list[DriftResult]:
        window_values: dict[str, list[Any]] = {}
        for feats in window_features:
            for col, vals in feats.items():
                window_values.setdefault(col, []).extend(vals)

        results: list[DriftResult] = []
        baseline_columns = baseline_stats["columns"]

        for col, base in baseline_columns.items():
            vals = window_values.get(col, [])
            total = len(vals)
            null_count = sum(1 for v in vals if _is_missing(v))
            window_null_rate = null_count / total if total else 0.0
            results.append(
                DriftResult(
                    metric_name="missing_rate_delta",
                    feature_name=col,
                    value=window_null_rate - base["null_rate"],
                    details={
                        "window_null_rate": window_null_rate,
                        "baseline_null_rate": base["null_rate"],
                    },
                )
            )

            clean_vals = [v for v in vals if not _is_missing(v)]
            if not clean_vals:
                continue

            if base["kind"] == "numeric":
                window_props = _bin_proportions(
                    [float(v) for v in clean_vals], base["bin_edges"]
                )
                psi = _psi(base["bin_proportions"], window_props)
                results.append(
                    DriftResult(
                        metric_name="psi",
                        feature_name=col,
                        value=psi,
                        details={"bin_edges": base["bin_edges"]},
                        is_drifted=bool(psi > _PSI_DRIFT_THRESHOLD),
                    )
                )
                if base["values_sample"]:
                    ks_stat, ks_p = scipy_stats.ks_2samp(base["values_sample"], clean_vals)
                    results.append(
                        DriftResult(
                            metric_name="ks_statistic",
                            feature_name=col,
                            value=float(ks_stat),
                            details={"p_value": float(ks_p)},
                            is_drifted=bool(ks_p < _KS_P_VALUE_THRESHOLD),
                        )
                    )
                    wasserstein = scipy_stats.wasserstein_distance(
                        base["values_sample"], clean_vals
                    )
                    results.append(
                        DriftResult(
                            metric_name="wasserstein_distance",
                            feature_name=col,
                            value=float(wasserstein),
                        )
                    )
            else:
                psi = _psi_categorical(base["distribution"], clean_vals)
                results.append(
                    DriftResult(
                        metric_name="psi",
                        feature_name=col,
                        value=psi,
                        details={"baseline_distribution": base["distribution"]},
                        is_drifted=bool(psi > _PSI_DRIFT_THRESHOLD),
                    )
                )

        baseline_cols = set(baseline_columns)
        window_cols = set(window_values)
        new_cols, missing_cols = window_cols - baseline_cols, baseline_cols - window_cols
        if new_cols or missing_cols:
            results.append(
                DriftResult(
                    metric_name="schema_drift",
                    value=1.0,
                    details={
                        "new_columns": sorted(new_cols),
                        "missing_columns": sorted(missing_cols),
                    },
                    is_drifted=True,
                )
            )

        return results

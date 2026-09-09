import random

import pandas as pd
import pytest

from nextphase.profilers.tabular import TabularProfiler


@pytest.fixture
def profiler():
    return TabularProfiler()


@pytest.fixture
def reference_df():
    random.seed(0)
    return pd.DataFrame(
        {
            "age": [random.gauss(40, 8) for _ in range(500)],
            "income": [random.gauss(55000, 10000) for _ in range(500)],
            "segment": random.choices(["a", "b", "c"], weights=[0.6, 0.3, 0.1], k=500),
        }
    )


def _window_features(profiler, df: pd.DataFrame) -> list[dict]:
    # Simulate each row arriving as its own event, like a per-request wrap() call.
    return [profiler.extract_features(df.iloc[[i]]) for i in range(len(df))]


def test_no_drift_when_window_matches_baseline(profiler, reference_df):
    baseline = profiler.compute_baseline_stats(reference_df)
    random.seed(1)
    similar_window = pd.DataFrame(
        {
            "age": [random.gauss(40, 8) for _ in range(200)],
            "income": [random.gauss(55000, 10000) for _ in range(200)],
            "segment": random.choices(["a", "b", "c"], weights=[0.6, 0.3, 0.1], k=200),
        }
    )
    results = profiler.compute_drift(baseline, _window_features(profiler, similar_window))

    psi_age = next(r for r in results if r.metric_name == "psi" and r.feature_name == "age")
    assert psi_age.value < 0.1
    assert psi_age.is_drifted is False


def test_detects_numeric_drift_via_psi_and_ks(profiler, reference_df):
    baseline = profiler.compute_baseline_stats(reference_df)
    random.seed(2)
    # income shifted up by ~4 standard deviations -> unambiguous drift
    drifted_window = pd.DataFrame(
        {
            "age": [random.gauss(40, 8) for _ in range(200)],
            "income": [random.gauss(95000, 10000) for _ in range(200)],
            "segment": random.choices(["a", "b", "c"], weights=[0.6, 0.3, 0.1], k=200),
        }
    )
    results = profiler.compute_drift(baseline, _window_features(profiler, drifted_window))

    psi_income = next(r for r in results if r.metric_name == "psi" and r.feature_name == "income")
    ks_income = next(
        r for r in results if r.metric_name == "ks_statistic" and r.feature_name == "income"
    )
    assert psi_income.value > 0.2
    assert psi_income.is_drifted
    assert ks_income.is_drifted


def test_detects_categorical_drift(profiler, reference_df):
    baseline = profiler.compute_baseline_stats(reference_df)
    # Fully inverted category distribution vs. baseline's a-heavy mix.
    drifted_window = pd.DataFrame(
        {
            "age": [40.0] * 200,
            "income": [55000.0] * 200,
            "segment": ["c"] * 180 + ["b"] * 20,
        }
    )
    results = profiler.compute_drift(baseline, _window_features(profiler, drifted_window))
    psi_segment = next(r for r in results if r.metric_name == "psi" and r.feature_name == "segment")
    assert psi_segment.value > 0.2
    assert psi_segment.is_drifted is True


def test_missing_rate_delta(profiler):
    ref = pd.DataFrame({"x": [1.0, 2.0, 3.0, None] * 25})  # 25% baseline null rate
    baseline = profiler.compute_baseline_stats(ref)

    window = pd.DataFrame({"x": [1.0, 2.0, None, None] * 25})  # 50% window null rate
    results = profiler.compute_drift(baseline, _window_features(profiler, window))
    missing = next(r for r in results if r.metric_name == "missing_rate_delta")
    assert missing.value == pytest.approx(0.25, abs=0.01)


def test_schema_drift_detects_new_and_missing_columns(profiler, reference_df):
    baseline = profiler.compute_baseline_stats(reference_df)
    window = pd.DataFrame({"age": [40.0] * 10, "new_feature": [1] * 10})
    results = profiler.compute_drift(baseline, _window_features(profiler, window))
    schema = next(r for r in results if r.metric_name == "schema_drift")
    assert schema.is_drifted is True
    assert "new_feature" in schema.details["new_columns"]
    assert "income" in schema.details["missing_columns"]

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import driftwatch as dw
from driftwatch.metrics.windowing import compute_drift_metrics
from driftwatch.profilers.tabular import TabularProfiler


@pytest.fixture(autouse=True)
def _isolated_tracking_uri(tmp_path):
    dw.set_tracking_uri(f"file:{tmp_path / 'runs'}")


def test_compute_drift_metrics_only_after_window_elapses():
    session = dw.init(model_name="loan-model", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 300}))
    monitored = session.wrap(lambda df: [0] * len(df))

    for _ in range(20):
        monitored(pd.DataFrame({"income": [95000.0]}))  # deliberately drifted
    session.flush()

    # Window hasn't fully elapsed yet -> nothing to compute.
    results_now = compute_drift_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler()
    )
    assert results_now == []

    # Pretend an hour has passed -> window is now closed.
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    results_later = compute_drift_metrics(
        store=session.store,
        session_id=session.session_id,
        profiler=TabularProfiler(),
        now=later,
    )
    assert len(results_later) > 0
    psi_income = next(
        r for r in results_later if r.metric_name == "psi" and r.feature_name == "income"
    )
    assert psi_income.value > 0.2

    stored = session.store.query_metrics(session.session_id, category="drift")
    assert len(stored) == len(results_later)


def test_compute_drift_metrics_does_not_duplicate_on_rerun():
    session = dw.init(model_name="loan-model-2", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 100}))
    monitored = session.wrap(lambda df: [0] * len(df))
    for _ in range(5):
        monitored(pd.DataFrame({"income": [51000.0]}))
    session.flush()

    later = datetime.now(timezone.utc) + timedelta(hours=1)
    first_run = compute_drift_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    second_run = compute_drift_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    assert len(first_run) > 0
    assert second_run == []  # already computed, no duplicates

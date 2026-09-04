from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import driftwatch as dw
from driftwatch.metrics.windowing import compute_window_metrics
from driftwatch.profilers.tabular import TabularProfiler


@pytest.fixture(autouse=True)
def _isolated_tracking_uri(tmp_path):
    dw.set_tracking_uri(f"file:{tmp_path / 'runs'}")


def test_compute_window_metrics_only_after_window_elapses():
    session = dw.init(model_name="loan-model", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 300}))
    monitored = session.wrap(lambda df: [0] * len(df))

    for _ in range(20):
        monitored(pd.DataFrame({"income": [95000.0]}))  # deliberately drifted
    session.flush()

    # Window hasn't fully elapsed yet -> nothing to compute.
    results_now = compute_window_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler()
    )
    assert results_now == []

    # Pretend an hour has passed -> window is now closed.
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    results_later = compute_window_metrics(
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

    label_coverage = next(r for r in results_later if r.metric_name == "label_coverage")
    assert label_coverage.value == 0.0  # no labels logged in this test

    duplicate_rate = next(r for r in results_later if r.metric_name == "duplicate_rate")
    assert duplicate_rate.value == pytest.approx(0.95)  # 20 identical rows -> 1 unique / 20

    stored_drift = session.store.query_metrics(session.session_id, category="drift")
    stored_quality = session.store.query_metrics(session.session_id, category="quality")
    stored_performance = session.store.query_metrics(session.session_id, category="performance")
    assert len(stored_drift) + len(stored_quality) + len(stored_performance) == len(results_later)


def test_compute_window_metrics_does_not_duplicate_on_rerun():
    session = dw.init(model_name="loan-model-2", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 100}))
    monitored = session.wrap(lambda df: [0] * len(df))
    for _ in range(5):
        monitored(pd.DataFrame({"income": [51000.0]}))
    session.flush()

    later = datetime.now(timezone.utc) + timedelta(hours=1)
    first_run = compute_window_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    second_run = compute_window_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    assert len(first_run) > 0
    assert second_run == []  # already computed, no duplicates


def test_compute_window_metrics_reflects_logged_labels():
    session = dw.init(model_name="loan-model-3", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 100}))

    request_ids = []
    monitored = session.wrap(lambda df: [1 if df.income.iloc[0] > 60000 else 0])
    for income in [50000.0, 70000.0, 55000.0, 80000.0]:
        monitored(pd.DataFrame({"income": [income]}))
    session.flush()
    events = session.store.query_events(session.session_id)
    request_ids = [e.request_id for e in events]

    # Ground truth matches the model's predictions for every request.
    y_true = []
    for e in events:
        income = e.input[0]["income"] if isinstance(e.input, list) else e.input["income"]
        y_true.append(1 if income > 60000 else 0)
    session.log_labels(request_ids, y_true)

    later = datetime.now(timezone.utc) + timedelta(hours=1)
    results = compute_window_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    label_coverage = next(r for r in results if r.metric_name == "label_coverage")
    assert label_coverage.value == pytest.approx(1.0)
    accuracy = next(r for r in results if r.metric_name == "accuracy")
    assert accuracy.value == pytest.approx(1.0)

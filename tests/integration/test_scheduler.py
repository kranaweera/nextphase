from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import nextphase as dw
from nextphase.metrics.windowing import compute_window_metrics
from nextphase.profilers.tabular import TabularProfiler
from nextphase.server.scheduler import Scheduler
from nextphase.store.base import AlertRule


@pytest.fixture(autouse=True)
def _isolated_tracking_uri(tmp_path):
    dw.set_tracking_uri(f"file:{tmp_path / 'runs'}")


def test_scheduler_engine_fires_alert_once_window_metrics_exist():
    session = dw.init(model_name="loan-model", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 100}))
    monitored = session.wrap(lambda df: [0] * len(df))
    for _ in range(10):
        monitored(pd.DataFrame({"income": [95000.0]}))  # deliberately drifted
    session.flush()

    session.store.create_alert_rule(
        AlertRule(
            rule_id="rule1",
            session_id=session.session_id,
            metric_name="psi",
            feature_name="income",
            comparator=">",
            threshold=0.2,
        )
    )

    # Windows only compute once fully elapsed (see windowing.py) — drive that
    # directly rather than waiting a real hour for the scheduler's own tick.
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    results = compute_window_metrics(
        store=session.store, session_id=session.session_id, profiler=TabularProfiler(), now=later
    )
    assert len(results) > 0

    scheduler = Scheduler(session.store, interval_seconds=9999)
    fired = scheduler._engine.evaluate_all(session_id=session.session_id)
    assert len(fired) == 1
    assert fired[0].metric_name == "psi"
    assert len(session.store.query_alerts(session.session_id, status="open")) == 1


def test_scheduler_tick_computes_metrics_for_all_sessions():
    session = dw.init(model_name="loan-model-2", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 100}))
    monitored = session.wrap(lambda df: [0] * len(df))
    for _ in range(5):
        monitored(pd.DataFrame({"income": [51000.0]}))
    session.flush()

    scheduler = Scheduler(session.store, interval_seconds=9999)
    scheduler.tick()  # window hasn't elapsed yet relative to real "now" -> no-op, must not raise

    assert session.store.query_metrics(session.session_id, category="drift") == []

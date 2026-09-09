from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from nextphase.store.base import (
    AlertRecord,
    AlertRule,
    EventRecord,
    MetricValueRecord,
    SessionRecord,
)
from nextphase.store.sqlite_store import LocalSQLiteStore


@pytest.fixture
def store(tmp_path):
    s = LocalSQLiteStore(root=tmp_path / "runs")
    yield s
    s.close()


def _make_session(store, session_id="s1") -> SessionRecord:
    session = SessionRecord(
        session_id=session_id,
        model_name="fraud-detector",
        modality="tabular",
        created_at=datetime.now(timezone.utc),
        tracking_uri=f"file:{store.root}",
        metadata={"owner": "kanishka"},
    )
    store.create_session(session)
    return session


def test_create_and_get_session(store):
    session = _make_session(store)
    fetched = store.get_session(session.session_id)
    assert fetched is not None
    assert fetched.model_name == "fraud-detector"
    assert fetched.metadata == {"owner": "kanishka"}


def test_list_sessions_filters_by_model_name(store):
    _make_session(store, "s1")
    other = SessionRecord(
        session_id="s2",
        model_name="churn-model",
        modality="text",
        created_at=datetime.now(timezone.utc),
        tracking_uri=f"file:{store.root}",
    )
    store.create_session(other)

    assert len(store.list_sessions()) == 2
    assert [s.session_id for s in store.list_sessions(model_name="churn-model")] == ["s2"]


def test_log_and_get_baseline(store):
    session = _make_session(store)
    ref_df = pd.DataFrame({"age": [30, 40, 50], "income": [50000, 60000, 70000]})

    baseline_id = store.log_baseline(
        session_id=session.session_id,
        schema={"age": "int64", "income": "int64"},
        summary_stats={"age": {"mean": 40.0}},
        reference_sample=ref_df,
        row_count=len(ref_df),
    )
    assert baseline_id

    baseline = store.get_baseline(session.session_id)
    assert baseline is not None
    assert baseline.row_count == 3
    assert baseline.summary_stats["age"]["mean"] == 40.0


def test_log_event_buffers_then_flushes_on_query(store):
    session = _make_session(store)
    now = datetime.now(timezone.utc)

    event = EventRecord(
        event_id="e1",
        session_id=session.session_id,
        request_id="r1",
        timestamp=now,
        status="ok",
        input={"age": 30, "income": 50000},
        output={"prediction": 0},
        latency_ms=12.3,
    )
    store.log_event(event)

    # Not flushed yet (below FLUSH_EVERY / FLUSH_INTERVAL_SECONDS) — direct
    # table read shouldn't see it, but query_events forces a flush first.
    events = store.query_events(session.session_id)
    assert len(events) == 1
    assert events[0].event_id == "e1"
    assert events[0].input == {"age": 30, "income": 50000}
    assert events[0].output == {"prediction": 0}
    assert events[0].latency_ms == pytest.approx(12.3)


def test_many_events_auto_flush_at_threshold(store):
    session = _make_session(store)
    now = datetime.now(timezone.utc)
    for i in range(150):
        store.log_event(
            EventRecord(
                event_id=f"e{i}",
                session_id=session.session_id,
                request_id=f"r{i}",
                timestamp=now + timedelta(seconds=i),
                status="ok",
                input={"x": i},
                output={"y": i * 2},
            )
        )
    events = store.query_events(session.session_id, limit=200)
    assert len(events) == 150


def test_log_and_get_labels(store):
    session = _make_session(store)
    store.log_labels(session.session_id, ["r1", "r2"], [1, 0])
    labels = store.get_labels(session.session_id, ["r1", "r2", "r3"])
    assert labels == {"r1": 1, "r2": 0}


def test_metric_values_roundtrip(store):
    session = _make_session(store)
    now = datetime.now(timezone.utc)
    store.log_metric_values(
        [
            MetricValueRecord(
                session_id=session.session_id,
                metric_category="drift",
                metric_name="psi",
                feature_name="age",
                window_start=now,
                window_end=now + timedelta(hours=1),
                value=0.25,
                details={"bins": 10},
            )
        ]
    )
    metrics = store.query_metrics(session.session_id, metric_name="psi")
    assert len(metrics) == 1
    assert metrics[0].value == pytest.approx(0.25)
    assert metrics[0].details == {"bins": 10}


def test_alert_rule_and_alert_lifecycle(store):
    session = _make_session(store)
    rule = AlertRule(
        rule_id="rule1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="age",
        comparator=">",
        threshold=0.2,
    )
    store.create_alert_rule(rule)
    assert [r.rule_id for r in store.list_alert_rules(session.session_id)] == ["rule1"]

    alert = AlertRecord(
        alert_id="alert1",
        rule_id="rule1",
        session_id=session.session_id,
        triggered_at=datetime.now(timezone.utc),
        metric_name="psi",
        observed_value=0.35,
        threshold=0.2,
    )
    store.log_alert(alert)
    open_alerts = store.query_alerts(session.session_id, status="open")
    assert len(open_alerts) == 1

    store.ack_alert("alert1")
    assert store.query_alerts(session.session_id, status="open") == []
    assert len(store.query_alerts(session.session_id, status="acknowledged")) == 1

    store.delete_alert_rule("rule1")
    assert store.list_alert_rules(session.session_id) == []

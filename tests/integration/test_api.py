from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import nextphase as dw
from nextphase.server.app import create_app
from nextphase.store.base import AlertRecord, AlertRule


@pytest.fixture
def api(tmp_path):
    uri = f"file:{tmp_path / 'runs'}"
    dw.set_tracking_uri(uri)
    session = dw.init(model_name="loan-model", modality="tabular")
    session.log_baseline(pd.DataFrame({"income": [50000.0] * 50}))
    monitored = session.wrap(lambda df: [0] * len(df))
    monitored(pd.DataFrame({"income": [55000.0]}))
    session.flush()

    app = create_app(uri, alert_interval_seconds=None)
    with TestClient(app) as client:
        client.session_id = session.session_id  # type: ignore[attr-defined]
        client.store = session.store  # type: ignore[attr-defined]
        yield client


def test_health(api):
    resp = api.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_sessions(api):
    resp = api.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["model_name"] == "loan-model"
    assert sessions[0]["event_count"] == 1
    assert sessions[0]["open_alert_count"] == 0


def test_list_sessions_filters_by_model_name(api):
    assert len(api.get("/api/sessions", params={"model_name": "loan-model"}).json()) == 1
    assert api.get("/api/sessions", params={"model_name": "nonexistent"}).json() == []


def test_get_session(api):
    resp = api.get(f"/api/sessions/{api.session_id}")
    assert resp.status_code == 200
    assert resp.json()["modality"] == "tabular"


def test_get_session_not_found(api):
    assert api.get("/api/sessions/does-not-exist").status_code == 404


def test_get_baseline(api):
    resp = api.get(f"/api/sessions/{api.session_id}/baseline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 50
    assert "income" in body["column_schema"]


def test_get_baseline_not_found(api):
    assert api.get("/api/sessions/does-not-exist/baseline").status_code == 404


def test_get_events(api):
    resp = api.get(f"/api/sessions/{api.session_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["status"] == "ok"


def test_get_metrics_empty_before_windowing_runs(api):
    resp = api.get(f"/api/sessions/{api.session_id}/metrics")
    assert resp.status_code == 200
    assert resp.json() == []


def test_alert_rule_crud(api):
    create_resp = api.post(
        f"/api/sessions/{api.session_id}/alert-rules",
        json={"metric_name": "psi", "feature_name": "income", "comparator": ">", "threshold": 0.2},
    )
    assert create_resp.status_code == 200
    rule_id = create_resp.json()["rule_id"]

    list_resp = api.get("/api/alert-rules", params={"session_id": api.session_id})
    assert len(list_resp.json()) == 1

    delete_resp = api.delete(f"/api/alert-rules/{rule_id}")
    assert delete_resp.status_code == 200
    assert api.get("/api/alert-rules", params={"session_id": api.session_id}).json() == []


def test_list_and_ack_alerts(api):
    rule = AlertRule(
        rule_id="rule1",
        session_id=api.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
    )
    api.store.create_alert_rule(rule)
    api.store.log_alert(
        AlertRecord(
            alert_id="alert1",
            rule_id="rule1",
            session_id=api.session_id,
            triggered_at=datetime.now(timezone.utc),
            metric_name="psi",
            observed_value=0.5,
            threshold=0.2,
        )
    )

    resp = api.get("/api/alerts", params={"session_id": api.session_id, "status": "open"})
    assert len(resp.json()) == 1

    ack_resp = api.post("/api/alerts/alert1/ack")
    assert ack_resp.status_code == 200
    open_after_ack = api.get(
        "/api/alerts", params={"session_id": api.session_id, "status": "open"}
    ).json()
    assert open_after_ack == []
    assert len(api.get("/api/alerts", params={"session_id": api.session_id}).json()) == 1

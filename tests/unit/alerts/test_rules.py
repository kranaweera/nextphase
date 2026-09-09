from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from nextphase.alerts.rules import AlertEngine
from nextphase.store.base import (
    AlertRecord,
    AlertRule,
    MetricValueRecord,
    SessionRecord,
)
from nextphase.store.sqlite_store import LocalSQLiteStore


class FakeNotifier:
    def __init__(self):
        self.calls: list[tuple[AlertRecord, dict[str, Any]]] = []

    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None:
        self.calls.append((alert, config))


class FailingNotifier:
    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None:
        raise RuntimeError("simulated notifier failure")


@pytest.fixture
def store(tmp_path):
    s = LocalSQLiteStore(root=tmp_path / "runs")
    yield s
    s.close()


@pytest.fixture
def session(store):
    record = SessionRecord(
        session_id="s1",
        model_name="loan-model",
        modality="tabular",
        created_at=datetime.now(timezone.utc),
        tracking_uri="file:./runs",
    )
    store.create_session(record)
    return record


def _log_windows(store, session_id: str, values: list[float], metric="psi", feature="income"):
    now = datetime.now(timezone.utc)
    for i, value in enumerate(values):
        window_start = now + timedelta(hours=i)
        store.log_metric_values(
            [
                MetricValueRecord(
                    session_id=session_id,
                    metric_category="drift",
                    metric_name=metric,
                    feature_name=feature,
                    window_start=window_start,
                    window_end=window_start + timedelta(hours=1),
                    value=value,
                )
            ]
        )


def test_fires_only_when_all_consecutive_windows_breach(store, session):
    _log_windows(store, session.session_id, [0.05, 0.1, 0.25, 0.3])  # last 2 breach 0.2
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        consecutive_windows=2,
    )
    engine = AlertEngine(store)
    alert = engine.evaluate_rule(rule)
    assert alert is not None
    assert alert.observed_value == pytest.approx(0.3)


def test_does_not_fire_when_only_some_windows_breach(store, session):
    _log_windows(store, session.session_id, [0.05, 0.3])  # only the latest breaches
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        consecutive_windows=2,
    )
    engine = AlertEngine(store)
    assert engine.evaluate_rule(rule) is None


def test_does_not_refire_for_the_same_window(store, session):
    _log_windows(store, session.session_id, [0.3])
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        consecutive_windows=1,
    )
    engine = AlertEngine(store)
    first = engine.evaluate_rule(rule)
    second = engine.evaluate_rule(rule)
    assert first is not None
    assert second is None
    assert len(store.query_alerts(session.session_id)) == 1


def test_disabled_rule_never_fires(store, session):
    _log_windows(store, session.session_id, [0.9])
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        enabled=False,
    )
    assert AlertEngine(store).evaluate_rule(rule) is None


def test_dispatches_to_configured_notifier(store, session):
    _log_windows(store, session.session_id, [0.3])
    fake = FakeNotifier()
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        notifiers=[{"type": "fake", "url": "https://example.test/hook"}],
    )
    engine = AlertEngine(store, notifiers={"fake": fake})
    alert = engine.evaluate_rule(rule)

    assert len(fake.calls) == 1
    dispatched_alert, config = fake.calls[0]
    assert dispatched_alert.alert_id == alert.alert_id
    assert config["url"] == "https://example.test/hook"


def test_notifier_failure_does_not_prevent_alert_from_being_recorded(store, session):
    _log_windows(store, session.session_id, [0.3])
    rule = AlertRule(
        rule_id="r1",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        notifiers=[{"type": "broken"}],
    )
    engine = AlertEngine(store, notifiers={"broken": FailingNotifier()})
    alert = engine.evaluate_rule(rule)  # must not raise
    assert alert is not None
    assert len(store.query_alerts(session.session_id)) == 1


def test_evaluate_all_only_considers_enabled_rules_for_the_session(store, session):
    _log_windows(store, session.session_id, [0.3])
    store.create_alert_rule(
        AlertRule(
            rule_id="enabled",
            session_id=session.session_id,
            metric_name="psi",
            feature_name="income",
            comparator=">",
            threshold=0.2,
        )
    )
    store.create_alert_rule(
        AlertRule(
            rule_id="disabled",
            session_id=session.session_id,
            metric_name="psi",
            feature_name="income",
            comparator=">",
            threshold=0.2,
            enabled=False,
        )
    )
    fired = AlertEngine(store).evaluate_all(session_id=session.session_id)
    assert len(fired) == 1
    assert fired[0].rule_id == "enabled"

"""Evaluates AlertRules against stored metric history and dispatches notifications.

A rule only fires when the last `consecutive_windows` computed windows for its
(metric_name, feature_name) *all* breach the threshold — this filters out
single-window noise. Each (rule, window) pair fires at most once: a firing is
recorded with the window it fired for in `AlertRecord.details`, and future
evaluations skip windows already alerted on.
"""

from __future__ import annotations

import logging
import operator
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from driftwatch.alerts.notifiers.base import Notifier
from driftwatch.store.base import AbstractStore, AlertRecord, AlertRule

logger = logging.getLogger(__name__)

_COMPARATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
}


class AlertEngine:
    def __init__(self, store: AbstractStore, notifiers: dict[str, Notifier] | None = None):
        self.store = store
        self.notifiers = notifiers or {}

    def evaluate_rule(self, rule: AlertRule) -> AlertRecord | None:
        if not rule.enabled:
            return None

        history = self.store.query_metrics(
            rule.session_id, metric_name=rule.metric_name, feature_name=rule.feature_name
        )
        if len(history) < rule.consecutive_windows:
            return None

        recent = sorted(history, key=lambda m: m.window_start)[-rule.consecutive_windows :]
        compare = _COMPARATORS[rule.comparator]
        if not all(compare(m.value, rule.threshold) for m in recent):
            return None

        latest = recent[-1]
        window_key = latest.window_start.isoformat()
        already_fired = any(
            a.rule_id == rule.rule_id and (a.details or {}).get("window_start") == window_key
            for a in self.store.query_alerts(session_id=rule.session_id)
        )
        if already_fired:
            return None

        alert = AlertRecord(
            alert_id=str(uuid.uuid4()),
            rule_id=rule.rule_id,
            session_id=rule.session_id,
            triggered_at=datetime.now(timezone.utc),
            metric_name=rule.metric_name,
            observed_value=latest.value,
            threshold=rule.threshold,
            details={"window_start": window_key, "feature_name": rule.feature_name},
        )
        self.store.log_alert(alert)
        self._dispatch(alert, rule)
        return alert

    def evaluate_all(self, session_id: str | None = None) -> list[AlertRecord]:
        fired = []
        for rule in self.store.list_alert_rules(session_id=session_id, enabled_only=True):
            alert = self.evaluate_rule(rule)
            if alert is not None:
                fired.append(alert)
        return fired

    def _dispatch(self, alert: AlertRecord, rule: AlertRule) -> None:
        for notifier_config in rule.notifiers:
            notifier = self.notifiers.get(notifier_config.get("type", ""))
            if notifier is None:
                logger.warning("No notifier registered for type %r", notifier_config.get("type"))
                continue
            try:
                notifier.notify(alert, notifier_config)
            except Exception:
                logger.exception("Notifier %r failed for alert %s", notifier_config, alert.alert_id)

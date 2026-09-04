from __future__ import annotations

from typing import Any

import httpx

from driftwatch.store.base import AlertRecord


class WebhookNotifier:
    """Generic notifier: POSTs a JSON payload to `config["url"]`."""

    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None:
        httpx.post(
            config["url"],
            json={
                "alert_id": alert.alert_id,
                "session_id": alert.session_id,
                "metric_name": alert.metric_name,
                "observed_value": alert.observed_value,
                "threshold": alert.threshold,
                "triggered_at": alert.triggered_at.isoformat(),
                "details": alert.details,
            },
            timeout=10.0,
        )

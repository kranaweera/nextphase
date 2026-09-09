from __future__ import annotations

from typing import Any

import httpx

from nextphase.store.base import AlertRecord


class SlackNotifier:
    """Posts to a Slack incoming-webhook URL (`config["url"]`)."""

    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None:
        text = (
            f":rotating_light: *{alert.metric_name}* breached threshold {alert.threshold} "
            f"(observed {alert.observed_value:.4f}) on session `{alert.session_id}`"
        )
        httpx.post(config["url"], json={"text": text}, timeout=10.0)

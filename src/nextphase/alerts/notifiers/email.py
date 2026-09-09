from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

from nextphase.store.base import AlertRecord


class EmailNotifier:
    """Sends via SMTP. Server credentials come from environment variables
    (never from the alert rule config, to keep secrets out of the store):
    NEXTPHASE_SMTP_HOST, NEXTPHASE_SMTP_PORT (default 587),
    NEXTPHASE_SMTP_USER, NEXTPHASE_SMTP_PASSWORD.
    `config["to_address"]` is required; `config["from_address"]` is optional.
    """

    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None:
        host = os.environ["NEXTPHASE_SMTP_HOST"]
        port = int(os.environ.get("NEXTPHASE_SMTP_PORT", "587"))
        user = os.environ.get("NEXTPHASE_SMTP_USER")
        password = os.environ.get("NEXTPHASE_SMTP_PASSWORD")

        msg = EmailMessage()
        msg["Subject"] = f"NextPhase alert: {alert.metric_name} breached threshold"
        msg["From"] = config.get("from_address", user or "nextphase@localhost")
        msg["To"] = config["to_address"]
        msg.set_content(
            f"{alert.metric_name} = {alert.observed_value:.4f} (threshold {alert.threshold}) "
            f"on session {alert.session_id} at {alert.triggered_at.isoformat()}"
        )

        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)

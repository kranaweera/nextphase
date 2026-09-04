from __future__ import annotations

from driftwatch.alerts.notifiers.base import Notifier
from driftwatch.alerts.notifiers.email import EmailNotifier
from driftwatch.alerts.notifiers.slack import SlackNotifier
from driftwatch.alerts.notifiers.webhook import WebhookNotifier

__all__ = ["Notifier", "WebhookNotifier", "SlackNotifier", "EmailNotifier", "get_default_notifiers"]


def get_default_notifiers() -> dict[str, Notifier]:
    """Maps an `AlertRule.notifiers[i]["type"]` value to the Notifier that handles it."""
    return {
        "webhook": WebhookNotifier(),
        "slack": SlackNotifier(),
        "email": EmailNotifier(),
    }

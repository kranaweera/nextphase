from __future__ import annotations

from typing import Any, Protocol

from driftwatch.store.base import AlertRecord


class Notifier(Protocol):
    def notify(self, alert: AlertRecord, config: dict[str, Any]) -> None: ...

"""Production backend stub: Postgres (metadata) + S3-compatible storage (payloads).

Not implemented in v1. This class exists to prove `AbstractStore` is a real
backend-agnostic interface — every method signature matches `LocalSQLiteStore`
exactly, so swapping backends later is a one-line `set_tracking_uri` change,
not a rewrite of calling code. See the roadmap in README.md / CHANGELOG.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from nextphase.store.base import (
    AbstractStore,
    AlertRecord,
    AlertRule,
    AlertStatus,
    BaselineRecord,
    EventRecord,
    MetricCategory,
    MetricValueRecord,
    SessionRecord,
)

_NOT_IMPLEMENTED = (
    "PostgresStore is not implemented yet — Postgres+S3 support is a planned "
    "fast-follow (see CHANGELOG.md roadmap). Use a `file:` tracking URI for now."
)


class PostgresStore(AbstractStore):
    def __init__(self, uri: str):
        self.uri = uri

    def create_session(self, session: SessionRecord) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_session(self, session_id: str) -> SessionRecord | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_sessions(self, model_name: str | None = None) -> list[SessionRecord]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def log_baseline(
        self,
        session_id: str,
        schema: dict[str, Any],
        summary_stats: dict[str, Any],
        reference_sample: Any,
        row_count: int,
    ) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_baseline(self, session_id: str) -> BaselineRecord | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def log_event(self, event: EventRecord) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def query_events(
        self,
        session_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventRecord]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def flush(self, session_id: str | None = None) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def log_labels(self, session_id: str, request_ids: list[str], y_true: list[Any]) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_labels(self, session_id: str, request_ids: list[str]) -> dict[str, Any]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def log_metric_values(self, values: list[MetricValueRecord]) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def query_metrics(
        self,
        session_id: str,
        metric_name: str | None = None,
        category: MetricCategory | None = None,
        feature_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MetricValueRecord]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def create_alert_rule(self, rule: AlertRule) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_alert_rules(
        self, session_id: str | None = None, enabled_only: bool = False
    ) -> list[AlertRule]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def delete_alert_rule(self, rule_id: str) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def log_alert(self, alert: AlertRecord) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def query_alerts(
        self, session_id: str | None = None, status: AlertStatus | None = None
    ) -> list[AlertRecord]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def ack_alert(self, alert_id: str) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

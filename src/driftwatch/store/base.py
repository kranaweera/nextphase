"""Backend-agnostic storage interface.

A concrete Store owns both structured metadata (sessions, metrics, alerts)
and raw payload storage (baseline samples, event inputs/outputs, embeddings).
`LocalSQLiteStore` is the only implementation shipped in v1; `PostgresStore`
implements this same interface to prove it's backend-agnostic without
committing v1 effort to a production backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Modality = Literal["tabular", "text", "image"]
MetricCategory = Literal["drift", "quality", "performance"]
AlertStatus = Literal["open", "acknowledged", "resolved"]
Comparator = Literal[">", ">=", "<", "<=", "=="]


@dataclass
class SessionRecord:
    session_id: str
    model_name: str
    modality: Modality
    created_at: datetime
    tracking_uri: str
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "active"


@dataclass
class BaselineRecord:
    baseline_id: str
    session_id: str
    created_at: datetime
    row_count: int
    schema: dict[str, Any]
    summary_stats: dict[str, Any]
    payload_path: str


@dataclass
class EventRecord:
    event_id: str
    session_id: str
    request_id: str
    timestamp: datetime
    status: str
    input: Any
    output: Any
    latency_ms: float | None = None
    features: dict[str, Any] | None = None


@dataclass
class MetricValueRecord:
    session_id: str
    metric_category: MetricCategory
    metric_name: str
    window_start: datetime
    window_end: datetime
    value: float
    feature_name: str | None = None
    details: dict[str, Any] | None = None
    computed_at: datetime | None = None


@dataclass
class AlertRule:
    rule_id: str
    session_id: str
    metric_name: str
    comparator: Comparator
    threshold: float
    feature_name: str | None = None
    window: str = "1h"
    consecutive_windows: int = 1
    enabled: bool = True
    notifiers: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class AlertRecord:
    alert_id: str
    rule_id: str
    session_id: str
    triggered_at: datetime
    metric_name: str
    observed_value: float
    threshold: float
    status: AlertStatus = "open"
    details: dict[str, Any] | None = None


class AbstractStore(ABC):
    # sessions
    @abstractmethod
    def create_session(self, session: SessionRecord) -> None: ...

    @abstractmethod
    def get_session(self, session_id: str) -> SessionRecord | None: ...

    @abstractmethod
    def list_sessions(self, model_name: str | None = None) -> list[SessionRecord]: ...

    # baseline
    @abstractmethod
    def log_baseline(
        self,
        session_id: str,
        schema: dict[str, Any],
        summary_stats: dict[str, Any],
        reference_sample: Any,
        row_count: int,
    ) -> str: ...

    @abstractmethod
    def get_baseline(self, session_id: str) -> BaselineRecord | None: ...

    # events
    @abstractmethod
    def log_event(self, event: EventRecord) -> None: ...

    @abstractmethod
    def query_events(
        self,
        session_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventRecord]: ...

    @abstractmethod
    def flush(self, session_id: str | None = None) -> None:
        """Force any buffered writes to durable storage."""

    # labels
    @abstractmethod
    def log_labels(self, session_id: str, request_ids: list[str], y_true: list[Any]) -> None: ...

    @abstractmethod
    def get_labels(self, session_id: str, request_ids: list[str]) -> dict[str, Any]: ...

    # metrics
    @abstractmethod
    def log_metric_values(self, values: list[MetricValueRecord]) -> None: ...

    @abstractmethod
    def query_metrics(
        self,
        session_id: str,
        metric_name: str | None = None,
        category: MetricCategory | None = None,
        feature_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MetricValueRecord]: ...

    # alert rules
    @abstractmethod
    def create_alert_rule(self, rule: AlertRule) -> str: ...

    @abstractmethod
    def list_alert_rules(
        self, session_id: str | None = None, enabled_only: bool = False
    ) -> list[AlertRule]: ...

    @abstractmethod
    def delete_alert_rule(self, rule_id: str) -> None: ...

    # alerts
    @abstractmethod
    def log_alert(self, alert: AlertRecord) -> str: ...

    @abstractmethod
    def query_alerts(
        self, session_id: str | None = None, status: AlertStatus | None = None
    ) -> list[AlertRecord]: ...

    @abstractmethod
    def ack_alert(self, alert_id: str) -> None: ...

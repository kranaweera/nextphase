"""Pydantic response/request models for the dashboard API.

Field names on the `*Out` models intentionally mirror the corresponding
store dataclass (`store/base.py`) so a record can be spread directly into
its schema (`AlertOut(**vars(alert_record))`) without a manual field-by-field
mapping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from nextphase.store.base import AlertStatus, Comparator, MetricCategory, Modality


class SessionOut(BaseModel):
    session_id: str
    model_name: str
    modality: Modality
    created_at: datetime
    tracking_uri: str
    metadata: dict[str, Any]
    status: str


class SessionSummaryOut(SessionOut):
    event_count: int
    last_event_at: datetime | None
    open_alert_count: int


class BaselineOut(BaseModel):
    baseline_id: str
    session_id: str
    created_at: datetime
    row_count: int
    column_schema: dict[str, Any]
    summary_stats: dict[str, Any]


class EventOut(BaseModel):
    event_id: str
    request_id: str
    timestamp: datetime
    status: str
    latency_ms: float | None
    input: Any
    output: Any


class MetricPointOut(BaseModel):
    session_id: str
    metric_category: MetricCategory
    metric_name: str
    feature_name: str | None
    window_start: datetime
    window_end: datetime
    value: float
    details: dict[str, Any] | None
    computed_at: datetime | None


class AlertRuleIn(BaseModel):
    metric_name: str
    comparator: Comparator
    threshold: float
    feature_name: str | None = None
    window: str = "1h"
    consecutive_windows: int = 1
    enabled: bool = True
    notifiers: list[dict[str, Any]] = []


class AlertRuleOut(BaseModel):
    rule_id: str
    session_id: str
    metric_name: str
    feature_name: str | None
    comparator: Comparator
    threshold: float
    window: str
    consecutive_windows: int
    enabled: bool
    notifiers: list[dict[str, Any]]
    created_at: datetime | None


class AlertOut(BaseModel):
    alert_id: str
    rule_id: str
    session_id: str
    triggered_at: datetime
    metric_name: str
    observed_value: float
    threshold: float
    status: AlertStatus
    details: dict[str, Any] | None

"""Local, zero-config store: SQLite for metadata, Parquet for payloads.

This is the default backend behind `file:./runs` tracking URIs. Event
payloads are buffered in memory per session and flushed together as a single
Parquet part file (one write, many rows) whenever the buffer reaches
`FLUSH_EVERY` events or `FLUSH_INTERVAL_SECONDS` has elapsed since the first
buffered event — trading a small amount of durability lag for near-zero
overhead on the inference hot path (see `Session.wrap`).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

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

FLUSH_EVERY = 100
FLUSH_INTERVAL_SECONDS = 5.0

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _json_default(obj: Any) -> Any:
    # Best-effort fallback for numpy/pandas scalars and other non-JSON-native types
    # without importing numpy/pandas here (keeps the store dependency-light).
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if hasattr(obj, "tolist"):  # numpy array / pandas Series/Index
        return obj.tolist()
    if hasattr(obj, "to_dict"):  # pandas DataFrame/Series
        return obj.to_dict(orient="records") if hasattr(obj, "columns") else obj.to_dict()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=_json_default)


class LocalSQLiteStore(AbstractStore):
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "payloads").mkdir(exist_ok=True)

        self._db_path = self.root / "nextphase.db"
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_PATH.read_text())
        self._conn.commit()

        self._lock = threading.RLock()
        self._event_buffers: dict[str, list[EventRecord]] = {}
        self._buffer_started_at: dict[str, float] = {}

    # ---------------------------------------------------------------- sessions

    def create_session(self, session: SessionRecord) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO sessions
                   (session_id, model_name, modality, created_at, tracking_uri,
                    metadata_json, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    session.model_name,
                    session.modality,
                    session.created_at.isoformat(),
                    session.tracking_uri,
                    _dumps(session.metadata),
                    session.status,
                ),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, model_name: str | None = None) -> list[SessionRecord]:
        with self._lock:
            if model_name:
                rows = self._conn.execute(
                    "SELECT * FROM sessions WHERE model_name = ? ORDER BY created_at DESC",
                    (model_name,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM sessions ORDER BY created_at DESC"
                ).fetchall()
        return [self._row_to_session(r) for r in rows]

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            session_id=row["session_id"],
            model_name=row["model_name"],
            modality=row["modality"],
            created_at=_parse_iso(row["created_at"]),
            tracking_uri=row["tracking_uri"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            status=row["status"],
        )

    # ---------------------------------------------------------------- baseline

    def log_baseline(
        self,
        session_id: str,
        schema: dict[str, Any],
        summary_stats: dict[str, Any],
        reference_sample: Any,
        row_count: int,
    ) -> str:
        baseline_id = str(uuid.uuid4())
        payload_dir = self.root / "payloads" / session_id / "baseline"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / "reference.parquet"

        table = _to_arrow_table(reference_sample)
        pq.write_table(table, payload_path)

        with self._lock:
            self._conn.execute(
                """INSERT INTO baselines
                   (baseline_id, session_id, created_at, row_count, schema_json,
                    summary_stats_json, payload_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    baseline_id,
                    session_id,
                    _now_iso(),
                    row_count,
                    _dumps(schema),
                    _dumps(summary_stats),
                    str(payload_path),
                ),
            )
            self._conn.commit()
        return baseline_id

    def get_baseline(self, session_id: str) -> BaselineRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM baselines WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return BaselineRecord(
            baseline_id=row["baseline_id"],
            session_id=row["session_id"],
            created_at=_parse_iso(row["created_at"]),
            row_count=row["row_count"],
            schema=json.loads(row["schema_json"]),
            summary_stats=json.loads(row["summary_stats_json"]),
            payload_path=row["payload_path"],
        )

    # ---------------------------------------------------------------- events

    def log_event(self, event: EventRecord) -> None:
        with self._lock:
            buf = self._event_buffers.setdefault(event.session_id, [])
            if not buf:
                self._buffer_started_at[event.session_id] = time.monotonic()
            buf.append(event)
            elapsed = time.monotonic() - self._buffer_started_at[event.session_id]
            if len(buf) >= FLUSH_EVERY or elapsed >= FLUSH_INTERVAL_SECONDS:
                self._flush_events(event.session_id)

    def flush(self, session_id: str | None = None) -> None:
        with self._lock:
            session_ids = [session_id] if session_id else list(self._event_buffers.keys())
            for sid in session_ids:
                if self._event_buffers.get(sid):
                    self._flush_events(sid)

    def _flush_events(self, session_id: str) -> None:
        """Caller must hold self._lock."""
        buf = self._event_buffers.get(session_id)
        if not buf:
            return

        now = datetime.now(timezone.utc)
        payload_dir = (
            self.root
            / "payloads"
            / session_id
            / "events"
            / f"date={now.strftime('%Y-%m-%d')}"
        )
        payload_dir.mkdir(parents=True, exist_ok=True)
        part_name = f"part-{now.strftime('%H')}-{uuid.uuid4().hex[:8]}.parquet"
        payload_path = payload_dir / part_name

        table = pa.table(
            {
                "event_id": [e.event_id for e in buf],
                "request_id": [e.request_id for e in buf],
                "timestamp": [e.timestamp.isoformat() for e in buf],
                "input_json": [_dumps(e.input) for e in buf],
                "output_json": [_dumps(e.output) for e in buf],
            }
        )
        pq.write_table(table, payload_path)

        rows = [
            (
                e.event_id,
                e.session_id,
                e.request_id,
                e.timestamp.isoformat(),
                e.latency_ms,
                e.status,
                str(payload_path),
                _dumps(e.features) if e.features is not None else None,
            )
            for e in buf
        ]
        self._conn.executemany(
            """INSERT INTO events
               (event_id, session_id, request_id, timestamp, latency_ms, status,
                payload_path, features_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

        self._event_buffers[session_id] = []
        self._buffer_started_at.pop(session_id, None)

    def query_events(
        self,
        session_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventRecord]:
        self.flush(session_id)  # make just-buffered events visible to readers

        clauses = ["session_id = ?"]
        params: list[Any] = [session_id]
        if start:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("timestamp < ?")
            params.append(end.isoformat())

        with self._lock:
            rows = self._conn.execute(
                f"""SELECT * FROM events WHERE {' AND '.join(clauses)}
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()

        by_path: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            by_path.setdefault(row["payload_path"], []).append(row)

        payloads_by_event: dict[str, tuple[Any, Any]] = {}
        for path, path_rows in by_path.items():
            wanted = {r["event_id"] for r in path_rows}
            pf = pq.read_table(path).to_pylist()
            for rec in pf:
                if rec["event_id"] in wanted:
                    payloads_by_event[rec["event_id"]] = (
                        json.loads(rec["input_json"]),
                        json.loads(rec["output_json"]),
                    )

        events = []
        for row in rows:
            input_payload, output_payload = payloads_by_event.get(row["event_id"], (None, None))
            events.append(
                EventRecord(
                    event_id=row["event_id"],
                    session_id=row["session_id"],
                    request_id=row["request_id"],
                    timestamp=_parse_iso(row["timestamp"]),
                    latency_ms=row["latency_ms"],
                    status=row["status"],
                    input=input_payload,
                    output=output_payload,
                    features=json.loads(row["features_json"]) if row["features_json"] else None,
                )
            )
        return events

    # ---------------------------------------------------------------- labels

    def log_labels(self, session_id: str, request_ids: list[str], y_true: list[Any]) -> None:
        if len(request_ids) != len(y_true):
            raise ValueError("request_ids and y_true must be the same length")
        rows = [
            (session_id, rid, _dumps(y), _now_iso())
            for rid, y in zip(request_ids, y_true, strict=True)
        ]
        with self._lock:
            self._conn.executemany(
                """INSERT INTO labels (session_id, request_id, y_true_json, logged_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(session_id, request_id) DO UPDATE SET
                     y_true_json = excluded.y_true_json, logged_at = excluded.logged_at""",
                rows,
            )
            self._conn.commit()

    def get_labels(self, session_id: str, request_ids: list[str]) -> dict[str, Any]:
        if not request_ids:
            return {}
        placeholders = ",".join("?" * len(request_ids))
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT request_id, y_true_json FROM labels
                    WHERE session_id = ? AND request_id IN ({placeholders})""",
                (session_id, *request_ids),
            ).fetchall()
        return {r["request_id"]: json.loads(r["y_true_json"]) for r in rows}

    # ---------------------------------------------------------------- metrics

    def log_metric_values(self, values: list[MetricValueRecord]) -> None:
        rows = [
            (
                v.session_id,
                v.metric_category,
                v.metric_name,
                v.feature_name,
                v.window_start.isoformat(),
                v.window_end.isoformat(),
                v.value,
                _dumps(v.details) if v.details is not None else None,
                (v.computed_at or datetime.now(timezone.utc)).isoformat(),
            )
            for v in values
        ]
        with self._lock:
            self._conn.executemany(
                """INSERT INTO metric_values
                   (session_id, metric_category, metric_name, feature_name,
                    window_start, window_end, value, details_json, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            self._conn.commit()

    def query_metrics(
        self,
        session_id: str,
        metric_name: str | None = None,
        category: MetricCategory | None = None,
        feature_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MetricValueRecord]:
        clauses = ["session_id = ?"]
        params: list[Any] = [session_id]
        if metric_name:
            clauses.append("metric_name = ?")
            params.append(metric_name)
        if category:
            clauses.append("metric_category = ?")
            params.append(category)
        if feature_name:
            clauses.append("feature_name = ?")
            params.append(feature_name)
        if start:
            clauses.append("window_start >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("window_end <= ?")
            params.append(end.isoformat())

        with self._lock:
            rows = self._conn.execute(
                f"""SELECT * FROM metric_values WHERE {' AND '.join(clauses)}
                    ORDER BY window_start ASC""",
                params,
            ).fetchall()

        return [
            MetricValueRecord(
                session_id=r["session_id"],
                metric_category=r["metric_category"],
                metric_name=r["metric_name"],
                feature_name=r["feature_name"],
                window_start=_parse_iso(r["window_start"]),
                window_end=_parse_iso(r["window_end"]),
                value=r["value"],
                details=json.loads(r["details_json"]) if r["details_json"] else None,
                computed_at=_parse_iso(r["computed_at"]),
            )
            for r in rows
        ]

    # ---------------------------------------------------------------- alert rules

    def create_alert_rule(self, rule: AlertRule) -> str:
        with self._lock:
            self._conn.execute(
                """INSERT INTO alert_rules
                   (rule_id, session_id, metric_name, feature_name, comparator, threshold,
                    window, consecutive_windows, enabled, notifiers_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rule.rule_id,
                    rule.session_id,
                    rule.metric_name,
                    rule.feature_name,
                    rule.comparator,
                    rule.threshold,
                    rule.window,
                    rule.consecutive_windows,
                    int(rule.enabled),
                    _dumps(rule.notifiers),
                    (rule.created_at or datetime.now(timezone.utc)).isoformat(),
                ),
            )
            self._conn.commit()
        return rule.rule_id

    def list_alert_rules(
        self, session_id: str | None = None, enabled_only: bool = False
    ) -> list[AlertRule]:
        clauses = []
        params: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if enabled_only:
            clauses.append("enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM alert_rules {where} ORDER BY created_at DESC", params
            ).fetchall()
        return [self._row_to_rule(r) for r in rows]

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> AlertRule:
        return AlertRule(
            rule_id=row["rule_id"],
            session_id=row["session_id"],
            metric_name=row["metric_name"],
            feature_name=row["feature_name"],
            comparator=row["comparator"],
            threshold=row["threshold"],
            window=row["window"],
            consecutive_windows=row["consecutive_windows"],
            enabled=bool(row["enabled"]),
            notifiers=json.loads(row["notifiers_json"] or "[]"),
            created_at=_parse_iso(row["created_at"]),
        )

    def delete_alert_rule(self, rule_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM alert_rules WHERE rule_id = ?", (rule_id,))
            self._conn.commit()

    # ---------------------------------------------------------------- alerts

    def log_alert(self, alert: AlertRecord) -> str:
        with self._lock:
            self._conn.execute(
                """INSERT INTO alerts
                   (alert_id, rule_id, session_id, triggered_at, metric_name,
                    observed_value, threshold, status, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert.alert_id,
                    alert.rule_id,
                    alert.session_id,
                    alert.triggered_at.isoformat(),
                    alert.metric_name,
                    alert.observed_value,
                    alert.threshold,
                    alert.status,
                    _dumps(alert.details) if alert.details is not None else None,
                ),
            )
            self._conn.commit()
        return alert.alert_id

    def query_alerts(
        self, session_id: str | None = None, status: AlertStatus | None = None
    ) -> list[AlertRecord]:
        clauses = []
        params: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM alerts {where} ORDER BY triggered_at DESC", params
            ).fetchall()
        return [
            AlertRecord(
                alert_id=r["alert_id"],
                rule_id=r["rule_id"],
                session_id=r["session_id"],
                triggered_at=_parse_iso(r["triggered_at"]),
                metric_name=r["metric_name"],
                observed_value=r["observed_value"],
                threshold=r["threshold"],
                status=r["status"],
                details=json.loads(r["details_json"]) if r["details_json"] else None,
            )
            for r in rows
        ]

    def ack_alert(self, alert_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE alerts SET status = 'acknowledged' WHERE alert_id = ?", (alert_id,)
            )
            self._conn.commit()

    def close(self) -> None:
        self.flush()
        with self._lock:
            self._conn.close()


def _to_arrow_table(reference_sample: Any) -> pa.Table:
    """Best-effort conversion of a reference dataset to an Arrow table for Parquet storage."""
    if isinstance(reference_sample, pa.Table):
        return reference_sample
    if hasattr(reference_sample, "to_dict") and hasattr(reference_sample, "columns"):
        # pandas DataFrame
        return pa.table(
            {col: reference_sample[col].tolist() for col in reference_sample.columns}
        )
    if (
        isinstance(reference_sample, list)
        and reference_sample
        and isinstance(reference_sample[0], str)
    ):
        return pa.table({"text": reference_sample})
    if isinstance(reference_sample, list):
        return pa.table({"value": [_dumps(v) for v in reference_sample]})
    raise TypeError(
        f"Don't know how to store a reference sample of type {type(reference_sample)!r}; "
        "pass a pandas DataFrame (tabular) or list[str] (text)."
    )

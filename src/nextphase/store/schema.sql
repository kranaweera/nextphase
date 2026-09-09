-- NextPhase local SQLite metadata schema.
-- Raw payloads (baseline samples, event inputs/outputs, embeddings) live in
-- Parquet files under <root>/payloads/; this schema stores structured
-- metadata plus pointers to those files.

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    model_name      TEXT NOT NULL,
    modality        TEXT NOT NULL CHECK (modality IN ('tabular', 'text', 'image')),
    created_at      TEXT NOT NULL,
    tracking_uri    TEXT NOT NULL,
    metadata_json   TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived'))
);

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id         TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions (session_id),
    created_at          TEXT NOT NULL,
    row_count           INTEGER,
    schema_json         TEXT NOT NULL,
    summary_stats_json  TEXT NOT NULL,
    payload_path        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_baselines_session ON baselines (session_id);

CREATE TABLE IF NOT EXISTS events (
    event_id            TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions (session_id),
    request_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    latency_ms          REAL,
    status               TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'error')),
    payload_path         TEXT NOT NULL,
    features_json         TEXT,
    UNIQUE (session_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events (session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_request_id ON events (session_id, request_id);

CREATE TABLE IF NOT EXISTS labels (
    session_id   TEXT NOT NULL REFERENCES sessions (session_id),
    request_id   TEXT NOT NULL,
    y_true_json  TEXT NOT NULL,
    logged_at    TEXT NOT NULL,
    PRIMARY KEY (session_id, request_id)
);

CREATE TABLE IF NOT EXISTS metric_values (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL REFERENCES sessions (session_id),
    metric_category  TEXT NOT NULL CHECK (metric_category IN ('drift', 'quality', 'performance')),
    metric_name      TEXT NOT NULL,
    feature_name     TEXT,
    window_start     TEXT NOT NULL,
    window_end       TEXT NOT NULL,
    value            REAL NOT NULL,
    details_json     TEXT,
    computed_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_session_window ON metric_values (session_id, window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metric_values (session_id, metric_name);

CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id               TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES sessions (session_id),
    metric_name           TEXT NOT NULL,
    feature_name          TEXT,
    comparator            TEXT NOT NULL CHECK (comparator IN ('>', '>=', '<', '<=', '==')),
    threshold             REAL NOT NULL,
    window                TEXT NOT NULL DEFAULT '1h',
    consecutive_windows   INTEGER NOT NULL DEFAULT 1,
    enabled               INTEGER NOT NULL DEFAULT 1,
    notifiers_json        TEXT,
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_session ON alert_rules (session_id);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL REFERENCES alert_rules (rule_id),
    session_id      TEXT NOT NULL REFERENCES sessions (session_id),
    triggered_at    TEXT NOT NULL,
    metric_name     TEXT NOT NULL,
    observed_value  REAL NOT NULL,
    threshold       REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    details_json    TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_session_status ON alerts (session_id, status);

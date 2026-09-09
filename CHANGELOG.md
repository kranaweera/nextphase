# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Core tracking API: `set_tracking_uri`, `init`, `Session.log_baseline`, `Session.wrap`,
  `Session.log_labels`. Model-agnostic — `wrap()` times and captures any callable's
  input/output without inspecting its internals.
- Local-first storage backend (`file:` tracking URIs): SQLite for structured metadata,
  Parquet for payloads/embeddings, buffered writes so `wrap()` stays cheap on the
  inference hot path. `PostgresStore` stubbed behind the same interface for a
  fast-follow production backend.
- Tabular drift profiler: PSI, KS-test, Wasserstein distance, missing-rate delta,
  schema drift.
- Text drift profiler: embedding centroid distance, sampled RBF-kernel MMD,
  length-shift KS-test, vocabulary Jensen-Shannon divergence + OOV rate. Pluggable
  `Embedder`, default `sentence-transformers` (optional `[text]` extra).
- Data-quality checks (duplicate rate, out-of-range rate, empty rate) and
  delayed-label performance metrics (accuracy/precision/recall/F1/AUC-ROC or
  MAE/RMSE, joined on `request_id` via `log_labels`).
- Windowed metric computation (`compute_window_metrics`): closes elapsed time
  windows, computes drift + quality + performance together, idempotent on rerun.
- FastAPI dashboard backend (`/api/sessions`, `/api/sessions/{id}/{baseline,events,
  metrics}`, `/api/alerts`, `/api/alert-rules`, `/api/health`).
- React (Vite + TypeScript) dashboard: Overview, Session Detail (drift/quality/
  performance tabs with per-metric time-series charts), and Alerts pages.
- Alerting: `AlertEngine` (fires only when the last N consecutive windows all
  breach a threshold, never re-fires for the same window), webhook/Slack/email
  notifiers, and a background scheduler running inside `nextphase ui`.
- `nextphase ui` CLI (Typer) — one command serves the API and the built dashboard.
- Image modality: interface-compatible `ImageProfiler` stub for a fast-follow release.

### Planned (not in this release)
- Real image-modality drift (CLIP/CNN-embedding centroid distance).
- Production `PostgresStore` + S3-compatible payload storage.
- Async/streaming model-callable support in `wrap()`.
- Standalone `nextphase worker` process for HA alert scheduling.

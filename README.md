# DriftWatch

Post-deployment monitoring for ML models — modality-agnostic (tabular, text, and soon image)
and model-agnostic (wraps any inference callable). Think NannyML's drift/performance math,
with MLflow's tracking-URI-and-dashboard ergonomics.

> **Status**: early alpha, under active development. APIs will change.

## Quickstart

```python
import driftwatch as dw

dw.set_tracking_uri("file:./runs")  # local, zero-config; Postgres/S3 planned

session = dw.init(model_name="fraud-detector-v3", modality="tabular")  # or "auto"
session.log_baseline(reference_df)  # training/reference distribution

monitored_model = session.wrap(model.predict)  # model-agnostic callable wrapper

# in your production inference path:
preds = monitored_model(X)  # transparently logs input, output, latency, timestamp

# later, once ground truth arrives:
session.log_labels(request_ids, y_true)
```

Launch the dashboard:

```bash
driftwatch ui --tracking-uri file:./runs --port 8000
```

## Why

[NannyML](https://github.com/NannyML/nannyml) pioneered post-deployment drift/performance
monitoring without ground truth, but is tabular-first. DriftWatch aims to bring the same
rigor to text (and eventually image) model deployments, behind a single wrapper API and a
dashboard you point at any inference pipeline, regardless of framework.

## Install

```bash
pip install -e ".[dev]"       # core + dev tooling
pip install -e ".[text]"      # + text-modality embeddings (sentence-transformers)
pip install -e ".[all]"       # everything
```

## Project layout

See `src/driftwatch/` for the package (`store/` — tracking backends, `profilers/` — per-modality
drift math, `metrics/` — quality & performance, `alerts/` — rule engine & notifiers, `server/` —
FastAPI dashboard backend) and `dashboard/` for the React frontend.

## License

Apache-2.0 — see [LICENSE](LICENSE).

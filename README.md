# NextPhase

Post-deployment monitoring for ML models — modality-agnostic (tabular, text, and soon image)
and model-agnostic (wraps any inference callable), with drift/performance math and a
tracking-URI-and-dashboard workflow built in.

> **Status**: early alpha, under active development. APIs will change.

## Quickstart

```python
import nextphase as dw

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
./scripts/build_dashboard.sh          # one-time (or after pulling dashboard/ changes):
                                       # builds the React app into src/nextphase/server/static/
nextphase ui --tracking-uri file:./runs --port 8000
```

> Running from source, `nextphase ui` has nothing to serve at `/` until you've
> run `build_dashboard.sh` at least once — you'll otherwise see a bare `{"detail":"Not
> Found"}` in the browser (the API itself, under `/api/*`, works either way). A
> PyPI install bundles the built dashboard already, so this step is source-only.

This serves the API and the web dashboard from one process (session grid, per-metric
drift/quality/performance time series, an alerts view) and also runs a background
scheduler that computes metrics for elapsed windows and evaluates alert rules
(`--alert-interval SECONDS`, default 300; `0` disables it).

### Alerting

```python
from nextphase.store.base import AlertRule

session.store.create_alert_rule(
    AlertRule(
        rule_id="income-psi",
        session_id=session.session_id,
        metric_name="psi",
        feature_name="income",
        comparator=">",
        threshold=0.2,
        consecutive_windows=2,  # only fire after 2 windows in a row breach
        notifiers=[{"type": "slack", "url": "https://hooks.slack.com/services/..."}],
    )
)
```

A rule fires once per breaching window (never twice for the same one) via a
webhook, Slack incoming-webhook, or SMTP email notifier.

## Why

Post-deployment drift/performance monitoring tends to be tabular-first. NextPhase aims to
bring the same rigor to text (and eventually image) model deployments, behind a single
wrapper API and a dashboard you point at any inference pipeline, regardless of framework.

## Install

```bash
pip install -e ".[dev]"       # core + dev tooling
pip install -e ".[text]"      # + text-modality embeddings (sentence-transformers)
pip install -e ".[all]"       # everything
```

## Examples

- [`examples/tabular_fraud_detector/`](examples/tabular_fraud_detector) — PSI/KS/Wasserstein
  drift on a drifting tabular feature.
- [`examples/text_sentiment_classifier/`](examples/text_sentiment_classifier) — embedding
  centroid/MMD/vocabulary drift on a topic shift.

## Project layout

See `src/nextphase/` for the package (`store/` — tracking backends, `profilers/` — per-modality
drift math, `metrics/` — quality & performance, `alerts/` — rule engine & notifiers, `server/` —
FastAPI dashboard backend) and `dashboard/` for the React frontend.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0 — see [LICENSE](LICENSE).

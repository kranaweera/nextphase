# Contributing to DriftWatch

Thanks for considering a contribution. This project is early-stage — expect the
API to move.

## Setup

```bash
git clone <this repo>
cd driftwatch
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,text]"

cd dashboard && npm install && cd ..
```

## Running checks

```bash
ruff check src tests examples   # lint
mypy src                        # type check
pytest                          # tests (fast; no network calls)

cd dashboard
npm run typecheck
npm run build
```

All four must pass before opening a PR — this is exactly what CI runs.

## Project layout

- `src/driftwatch/` — the Python package. See `store/` for the tracking backend,
  `profilers/` for per-modality drift math, `metrics/` for quality/performance/
  windowing, `alerts/` for the rule engine and notifiers, `server/` for the
  FastAPI dashboard backend.
- `dashboard/` — the React dashboard frontend (Vite + TypeScript).
- `examples/` — runnable end-to-end examples; a good place to sanity-check a
  change against real (if synthetic) usage before opening a PR.
- `tests/unit/` — fast, isolated tests (no I/O beyond a tmp SQLite file).
  `tests/integration/` — exercises the full wrap() -> store -> API path.

## Adding a new modality profiler

Implement the `Profiler` ABC in `profilers/base.py`
(`extract_features`, `compute_baseline_stats`, `compute_drift`), register it in
`profilers/get_profiler()`, and add both a unit test (synthetic drifted vs.
non-drifted data) and an example under `examples/`. `profilers/image.py` is a
stub showing the expected shape.

## Commit / PR conventions

- Keep changes scoped; prefer several small PRs over one large one.
- Add or update tests for any behavior change.
- Run the checks above locally — CI will re-run them, but faster feedback is
  faster feedback.

## Reporting bugs / proposing features

Open an issue with a minimal repro (a snippet using `driftwatch.init(...)` is
usually enough) or a clear description of the use case for a feature request.

"""End-to-end example: monitor a tabular fraud-detection model with DriftWatch.

Run with:  python train_and_monitor.py
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pandas as pd

import driftwatch as dw
from driftwatch.metrics.windowing import compute_drift_metrics
from driftwatch.profilers.tabular import TabularProfiler


def fake_model(X: pd.DataFrame) -> list[int]:
    """Stand-in for a real sklearn/PyTorch/HTTP model — any callable works."""
    return [1 if row.income > 60000 else 0 for row in X.itertuples()]


def main() -> None:
    dw.set_tracking_uri("file:./runs")
    session = dw.init(model_name="fraud-detector-v3", modality="tabular")

    random.seed(0)
    reference = pd.DataFrame(
        {
            "age": [random.randint(20, 60) for _ in range(500)],
            "income": [random.gauss(55000, 10000) for _ in range(500)],
        }
    )
    session.log_baseline(reference)

    monitored_model = session.wrap(fake_model)

    print("Simulating production traffic with income drifting upward...")
    for _ in range(200):
        drift_factor = 1.6  # a clear post-deployment shift vs. the reference set
        row = pd.DataFrame(
            {
                "age": [random.randint(20, 60)],
                "income": [random.gauss(55000 * drift_factor, 10000)],
            }
        )
        monitored_model(row)
    session.flush()

    # Metrics are only computed for windows that have fully elapsed; since this
    # demo runs in seconds, we pass a `now` an hour ahead to close the current
    # window. In production, this runs on a schedule against the real clock.
    results = compute_drift_metrics(
        store=session.store,
        session_id=session.session_id,
        profiler=TabularProfiler(),
        window="1h",
        now=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    print(f"\n{len(results)} drift metrics computed for session {session.session_id}:\n")
    for r in sorted(results, key=lambda x: (x.feature_name or "", x.metric_name)):
        is_drifted = bool((r.details or {}).get("is_drifted"))
        flag = " <- DRIFTED" if is_drifted else ""
        print(f"  {r.metric_name:22s} {r.feature_name or '-':10s} {r.value:>10.4f}{flag}")

    print("\nRun `driftwatch ui --tracking-uri file:./runs` to explore this session.")


if __name__ == "__main__":
    main()

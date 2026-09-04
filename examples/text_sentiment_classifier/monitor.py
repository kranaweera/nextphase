"""End-to-end example: monitor a text classifier with DriftWatch.

Uses the default embedder (`sentence-transformers`, downloaded on first
run) to detect a topic shift between the reference set and production
traffic. Requires: pip install "driftwatch[text]"

Run with:  python monitor.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import driftwatch as dw
from driftwatch.metrics.windowing import compute_window_metrics

REFERENCE_REVIEWS = [
    "the coffee machine broke again this morning",
    "great espresso and friendly staff at the cafe",
    "my order of a latte was delayed by ten minutes",
    "the barista made a wonderful cappuccino today",
    "coffee shop was out of oat milk for my order",
    "loved the cozy seating and quiet atmosphere here",
    "the cold brew was way too bitter for my taste",
    "friendly service but the wifi kept disconnecting",
] * 5  # 40 short "coffee shop review" documents

DRIFTED_SUPPORT_TICKETS = [
    "I cannot reset my password, the reset link is broken",
    "my subscription was charged twice this month please refund",
    "the app crashes every time I try to upload a file",
    "how do I export my account data to a spreadsheet",
    "your API is returning a 500 error on every request",
    "I need to cancel my plan before the renewal date",
] * 6  # ~36 unrelated "support ticket" documents


def fake_classifier(texts: list[str]) -> list[str]:
    """Stand-in for a real sentiment/topic classifier — any callable works."""
    return ["positive" if "great" in t or "wonderful" in t else "neutral" for t in texts]


def main() -> None:
    dw.set_tracking_uri("file:./runs")
    session = dw.init(model_name="review-classifier-v1", modality="text")
    session.log_baseline(REFERENCE_REVIEWS)

    monitored = session.wrap(fake_classifier)

    print("Simulating a shift from coffee-shop reviews to support tickets...")
    for text in DRIFTED_SUPPORT_TICKETS:
        monitored([text])
    session.flush()

    # See train_and_monitor.py in the tabular example for why `now` is
    # pushed an hour ahead: metrics only compute for fully-elapsed windows.
    results = compute_window_metrics(
        store=session.store,
        session_id=session.session_id,
        profiler=session.profiler,
        window="1h",
        now=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    print(f"\n{len(results)} metrics computed for session {session.session_id}:\n")
    for r in sorted(results, key=lambda x: x.metric_name):
        is_drifted = bool((r.details or {}).get("is_drifted"))
        flag = " <- DRIFTED" if is_drifted else ""
        print(f"  {r.metric_name:28s} {r.value:>10.4f}{flag}")

    print("\nRun `driftwatch ui --tracking-uri file:./runs` to explore this session.")


if __name__ == "__main__":
    main()

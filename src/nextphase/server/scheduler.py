"""Background loop run inside `nextphase ui`: closes elapsed windows,
computes drift/quality/performance metrics, and evaluates alert rules for
every session under this tracking URI. Metrics are windowed rollups by
design (see windowing.py), so this runs on an interval rather than per-event.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from nextphase.alerts.notifiers import get_default_notifiers
from nextphase.alerts.rules import AlertEngine
from nextphase.metrics.windowing import compute_window_metrics
from nextphase.profilers import get_profiler
from nextphase.store.base import AbstractStore

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300.0


class Scheduler:
    def __init__(self, store: AbstractStore, interval_seconds: float = DEFAULT_INTERVAL_SECONDS):
        self.store = store
        self.interval_seconds = interval_seconds
        self._engine = AlertEngine(store, notifiers=get_default_notifiers())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Scheduler tick failed")
            self._stop.wait(self.interval_seconds)

    def tick(self) -> None:
        now = datetime.now(timezone.utc)
        for session in self.store.list_sessions():
            try:
                profiler = get_profiler(session.modality)
            except ValueError:
                continue  # unsupported modality (shouldn't happen for a persisted session)
            compute_window_metrics(self.store, session.session_id, profiler, now=now)
            self._engine.evaluate_all(session_id=session.session_id)

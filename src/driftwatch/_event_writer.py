"""Background thread that drains a Session's event queue into its Store.

Keeping this off the calling thread is what lets `ModelWrapper.__call__` add
effectively no latency to the wrapped inference call.
"""

from __future__ import annotations

import queue
import threading

from driftwatch.store.base import AbstractStore, EventRecord

_POLL_TIMEOUT_SECONDS = 0.5


class EventWriter:
    def __init__(self, store: AbstractStore):
        self._store = store
        self._queue: queue.Queue[EventRecord] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def enqueue(self, event: EventRecord) -> None:
        self._ensure_started()
        self._queue.put(event)

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()

    def _run(self) -> None:
        while not (self._stop.is_set() and self._queue.empty()):
            try:
                event = self._queue.get(timeout=_POLL_TIMEOUT_SECONDS)
            except queue.Empty:
                continue
            self._store.log_event(event)
            self._queue.task_done()

    def flush(self) -> None:
        self._queue.join()

    def stop(self) -> None:
        self.flush()
        self._stop.set()

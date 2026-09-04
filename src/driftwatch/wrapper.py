"""Model-agnostic inference wrapper.

`ModelWrapper` never inspects model internals — it only times a call,
captures the arguments as "input" and the return value as "output", and
hands the event off to the owning `Session`. That's what makes it work
identically for sklearn `.predict`, a PyTorch `forward`, a HuggingFace
pipeline call, or a plain HTTP client call.
"""

from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from driftwatch.session import Session


def _capture_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if len(args) == 1 and not kwargs:
        return args[0]
    if not args and kwargs:
        return kwargs
    return {"args": list(args), "kwargs": kwargs}


class ModelWrapper:
    def __init__(self, fn: Callable[..., Any], session: Session):
        if inspect.iscoroutinefunction(fn):
            raise NotImplementedError(
                "driftwatch does not support wrapping async callables in v1; "
                "wrap a synchronous function instead."
            )
        self._fn = fn
        self._session = session

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        request_id = str(uuid.uuid4())
        t0 = time.perf_counter()
        try:
            result = self._fn(*args, **kwargs)
        except Exception:
            latency_ms = (time.perf_counter() - t0) * 1000
            self._log(request_id, args, kwargs, output=None, latency_ms=latency_ms, status="error")
            raise
        latency_ms = (time.perf_counter() - t0) * 1000
        self._log(request_id, args, kwargs, output=result, latency_ms=latency_ms, status="ok")
        return result

    def _log(
        self,
        request_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        output: Any,
        latency_ms: float,
        status: str,
    ) -> None:
        from driftwatch.store.base import EventRecord

        event = EventRecord(
            event_id=str(uuid.uuid4()),
            session_id=self._session.session_id,
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            status=status,
            input=_capture_input(args, kwargs),
            output=output,
            latency_ms=latency_ms,
        )
        self._session._enqueue_event(event)

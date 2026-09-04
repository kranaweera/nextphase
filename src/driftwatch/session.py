"""The `Session` object returned by `driftwatch.init(...)`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from driftwatch._event_writer import EventWriter
from driftwatch.profilers.detect import detect_modality
from driftwatch.store.base import AbstractStore, EventRecord, Modality, SessionRecord
from driftwatch.wrapper import ModelWrapper


def _default_profiler(modality: Modality) -> Any:
    if modality == "tabular":
        from driftwatch.profilers.tabular import TabularProfiler

        return TabularProfiler()
    if modality == "text":
        from driftwatch.profilers.text import TextProfiler

        return TextProfiler()
    if modality == "image":
        from driftwatch.profilers.image import ImageProfiler

        return ImageProfiler()
    raise ValueError(f"Unsupported modality: {modality!r}")


def _infer_schema(reference_data: Any, modality: Modality) -> dict[str, Any]:
    if modality == "tabular":
        if hasattr(reference_data, "dtypes"):  # pandas DataFrame
            return {col: str(dtype) for col, dtype in reference_data.dtypes.items()}
        raise TypeError(
            f"Tabular reference_data must be a pandas DataFrame, got {type(reference_data)!r}"
        )
    if modality == "text":
        if isinstance(reference_data, list) and all(isinstance(x, str) for x in reference_data):
            return {"type": "text"}
        raise TypeError(
            f"Text reference_data must be a list[str], got {type(reference_data)!r}"
        )
    raise ValueError(f"Unsupported modality: {modality!r}")


class Session:
    def __init__(
        self,
        store: AbstractStore,
        session_id: str,
        model_name: str,
        modality: str,
        tracking_uri: str,
        tags: dict[str, Any] | None = None,
        task_type: str | None = None,
        profiler: Any | None = None,
    ):
        self.store = store
        self.session_id = session_id
        self.model_name = model_name
        self.modality = modality
        self.tracking_uri = tracking_uri
        self.tags = tags or {}
        self.task_type = task_type
        self.created_at = datetime.now(timezone.utc)

        self._persisted = False
        self._writer = EventWriter(store)
        self._profiler = profiler

    @property
    def profiler(self) -> Any:
        """The Profiler this session uses for baseline stats and drift computation.

        Resolved (and cached) on first access, once modality is known — either
        the one passed to `driftwatch.init(profiler=...)`, or the default for
        this session's modality. Reusing the same instance for `log_baseline`
        and windowing keeps e.g. a custom text Embedder consistent everywhere.
        """
        if self._profiler is None:
            if self.modality == "auto":
                raise RuntimeError(
                    "Session modality is still 'auto' — call log_baseline(...) first."
                )
            self._profiler = _default_profiler(self.modality)  # type: ignore[arg-type]
        return self._profiler

    def _ensure_persisted(self) -> None:
        if self._persisted:
            return
        if self.modality == "auto":
            raise RuntimeError(
                "Session modality is still 'auto'. Call log_baseline(reference_data) first "
                "so DriftWatch can detect it, or pass modality= explicitly to driftwatch.init()."
            )
        self.store.create_session(
            SessionRecord(
                session_id=self.session_id,
                model_name=self.model_name,
                modality=self.modality,  # type: ignore[arg-type]
                created_at=self.created_at,
                tracking_uri=self.tracking_uri,
                metadata=self.tags,
            )
        )
        self._persisted = True

    def log_baseline(self, reference_data: Any) -> str:
        if self.modality == "auto":
            self.modality = detect_modality(reference_data)
        self._ensure_persisted()

        schema = _infer_schema(reference_data, self.modality)  # type: ignore[arg-type]
        summary_stats = self.profiler.compute_baseline_stats(reference_data)
        return self.store.log_baseline(
            session_id=self.session_id,
            schema=schema,
            summary_stats=summary_stats,
            reference_sample=reference_data,
            row_count=len(reference_data),
        )

    def wrap(self, fn: Any) -> ModelWrapper:
        self._ensure_persisted()
        return ModelWrapper(fn, self)

    def log_labels(self, request_ids: list[str], y_true: list[Any]) -> None:
        self.store.log_labels(self.session_id, list(request_ids), list(y_true))

    def _enqueue_event(self, event: EventRecord) -> None:
        self._writer.enqueue(event)

    def flush(self) -> None:
        self._writer.flush()
        self.store.flush(self.session_id)

    def close(self) -> None:
        self._writer.stop()
        self.store.flush(self.session_id)

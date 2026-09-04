"""Module-level tracking-URI state, mirroring `mlflow.set_tracking_uri`."""

from __future__ import annotations

from driftwatch.store.base import AbstractStore
from driftwatch.store.uri import DEFAULT_TRACKING_URI, resolve_store

_tracking_uri: str = DEFAULT_TRACKING_URI
_store_cache: dict[str, AbstractStore] = {}


def set_tracking_uri(uri: str) -> None:
    global _tracking_uri
    _tracking_uri = uri


def get_tracking_uri() -> str:
    return _tracking_uri


def get_store(uri: str | None = None) -> AbstractStore:
    """Return the (cached) store for `uri`, or the current global tracking URI."""
    target = uri or _tracking_uri
    if target not in _store_cache:
        _store_cache[target] = resolve_store(target)
    return _store_cache[target]

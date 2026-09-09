"""Tracking URI parsing: `set_tracking_uri("file:./runs")` -> a Store instance."""

from __future__ import annotations

from urllib.parse import urlsplit

from nextphase.store.base import AbstractStore

DEFAULT_TRACKING_URI = "file:./runs"


def resolve_store(uri: str) -> AbstractStore:
    parsed = urlsplit(uri)
    scheme = parsed.scheme or "file"

    if scheme == "file":
        # "file:./runs", "file:runs", "file:///abs/path" all resolve to a local path.
        path = uri.split(":", 1)[1] if ":" in uri else uri
        path = path.lstrip("/") if uri.startswith("file:///") else path
        from nextphase.store.sqlite_store import LocalSQLiteStore

        return LocalSQLiteStore(root=path or ".")

    if scheme in ("postgres", "postgresql"):
        from nextphase.store.postgres_store import PostgresStore

        return PostgresStore(uri)

    raise ValueError(
        f"Unsupported tracking URI scheme {scheme!r} (from {uri!r}). "
        "Supported in v1: 'file:'. 'postgresql:' is stubbed for a future release."
    )

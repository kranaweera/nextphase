from __future__ import annotations

from fastapi import Request

from driftwatch.store.base import AbstractStore


def get_store(request: Request) -> AbstractStore:
    return request.app.state.store

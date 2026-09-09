from __future__ import annotations

from fastapi import Request

from nextphase.store.base import AbstractStore


def get_store(request: Request) -> AbstractStore:
    return request.app.state.store

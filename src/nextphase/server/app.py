"""FastAPI app factory: the NextPhase dashboard API, plus the built React
SPA when present — one process, one port.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from nextphase import __version__
from nextphase.config import get_store
from nextphase.server.routes import alerts, health, sessions
from nextphase.server.scheduler import Scheduler

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(tracking_uri: str, alert_interval_seconds: float | None = 300.0) -> FastAPI:
    """`alert_interval_seconds=None` disables the background scheduler
    (windowing + alert evaluation) — useful for tests that don't want a
    background thread running against a short-lived store."""
    store = get_store(tracking_uri)
    scheduler = (
        Scheduler(store, interval_seconds=alert_interval_seconds)
        if alert_interval_seconds
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if scheduler is not None:
            scheduler.start()
        yield
        if scheduler is not None:
            scheduler.stop()

    app = FastAPI(title="NextPhase", version=__version__, lifespan=lifespan)
    app.state.tracking_uri = tracking_uri
    app.state.store = store
    app.state.scheduler = scheduler

    app.include_router(health.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(alerts.router, prefix="/api")

    index_html = _STATIC_DIR / "index.html"
    if index_html.exists():
        assets_dir = _STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            candidate = _STATIC_DIR / full_path
            return FileResponse(candidate if candidate.is_file() else index_html)

    return app

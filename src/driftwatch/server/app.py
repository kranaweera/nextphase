"""FastAPI app factory: the DriftWatch dashboard API, plus the built React
SPA when present (mounted the same way `mlflow ui` serves its frontend —
one process, one port).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from driftwatch import __version__
from driftwatch.config import get_store
from driftwatch.server.routes import alerts, health, sessions

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(tracking_uri: str) -> FastAPI:
    app = FastAPI(title="DriftWatch", version=__version__)
    app.state.tracking_uri = tracking_uri
    app.state.store = get_store(tracking_uri)

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

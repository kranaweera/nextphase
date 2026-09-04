from __future__ import annotations

import typer
import uvicorn

from driftwatch.server.app import create_app

app = typer.Typer(add_completion=False, help="DriftWatch: post-deployment ML monitoring.")


@app.callback()
def _main() -> None:
    """DriftWatch: post-deployment ML monitoring."""


@app.command()
def ui(
    tracking_uri: str = typer.Option(
        "file:./runs", "--tracking-uri", help="Tracking URI to serve (e.g. file:./runs)."
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Launch the DriftWatch dashboard (API + web UI) for a tracking URI."""
    fastapi_app = create_app(tracking_uri)
    uvicorn.run(fastapi_app, host=host, port=port)


if __name__ == "__main__":
    app()

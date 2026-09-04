"""DriftWatch: modality-agnostic, model-agnostic post-deployment ML monitoring."""

import uuid
from typing import Any

from driftwatch.config import get_store, get_tracking_uri, set_tracking_uri
from driftwatch.session import Session

__version__ = "0.1.0.dev0"

__all__ = ["__version__", "set_tracking_uri", "get_tracking_uri", "init", "Session"]


def init(
    model_name: str,
    modality: str = "auto",
    tags: dict[str, Any] | None = None,
    task_type: str | None = None,
) -> Session:
    """Start a monitoring session for a deployed model.

    `modality` may be `"tabular"`, `"text"`, `"image"`, or `"auto"` (resolved
    from the first call to `log_baseline`).
    """
    store = get_store()
    return Session(
        store=store,
        session_id=str(uuid.uuid4()),
        model_name=model_name,
        modality=modality,
        tracking_uri=get_tracking_uri(),
        tags=tags,
        task_type=task_type,
    )

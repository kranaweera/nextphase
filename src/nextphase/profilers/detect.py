"""Heuristic modality auto-detection for `nextphase.init(modality="auto")`."""

from __future__ import annotations

from typing import Any

from nextphase.store.base import Modality


def detect_modality(sample: Any) -> Modality:
    if isinstance(sample, str):
        return "text"
    if isinstance(sample, list) and sample and all(isinstance(x, str) for x in sample):
        return "text"
    if hasattr(sample, "columns") and hasattr(sample, "dtypes"):  # pandas DataFrame
        return "tabular"
    if isinstance(sample, dict):
        return "tabular"
    raise ValueError(
        f"Could not auto-detect modality for input of type {type(sample)!r}. "
        "Pass modality= explicitly to nextphase.init(...)."
    )

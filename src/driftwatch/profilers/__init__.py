"""Modality -> Profiler resolution."""

from __future__ import annotations

from driftwatch.profilers.base import DriftResult, Profiler
from driftwatch.store.base import Modality

__all__ = ["DriftResult", "Profiler", "get_profiler"]


def get_profiler(modality: Modality) -> Profiler:
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

"""Modality -> Profiler resolution."""

from __future__ import annotations

from nextphase.profilers.base import DriftResult, Profiler
from nextphase.store.base import Modality

__all__ = ["DriftResult", "Profiler", "get_profiler"]


def get_profiler(modality: Modality) -> Profiler:
    if modality == "tabular":
        from nextphase.profilers.tabular import TabularProfiler

        return TabularProfiler()
    if modality == "text":
        from nextphase.profilers.text import TextProfiler

        return TextProfiler()
    if modality == "image":
        from nextphase.profilers.image import ImageProfiler

        return ImageProfiler()
    raise ValueError(f"Unsupported modality: {modality!r}")

"""Image drift profiler — not implemented in v1.

Documents the intended shape: baseline/window images are embedded via a
pluggable extractor (CLIP or a user-supplied CNN feature extractor,
mirroring `profilers.text.Embedder`), and drift is measured as centroid
distance in embedding space — the same approach as `TextProfiler`. Kept as
a stub so `Profiler` proves out as a real backend-agnostic interface before
a second and third modality are built on top of it.
"""

from __future__ import annotations

from typing import Any

from driftwatch.profilers.base import DriftResult, Profiler

_NOT_IMPLEMENTED = (
    "Image modality support is planned as a fast-follow (see CHANGELOG.md "
    "roadmap): CLIP/CNN-embedding centroid drift, mirroring TextProfiler."
)


class ImageProfiler(Profiler):
    modality = "image"

    def extract_features(self, raw_input: Any) -> dict[str, Any]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def compute_baseline_stats(self, reference_data: Any) -> dict[str, Any]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def compute_drift(
        self, baseline_stats: dict[str, Any], window_features: list[dict[str, Any]]
    ) -> list[DriftResult]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

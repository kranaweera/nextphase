"""The modality plugin interface.

Every modality (tabular, text, and eventually image) implements this same
three-method contract, so the session/wrapper/windowing code above never
needs to know which modality it's dealing with.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class DriftResult:
    metric_name: str
    value: float
    feature_name: str | None = None
    details: dict[str, Any] | None = None
    is_drifted: bool | None = None


class Profiler(ABC):
    modality: ClassVar[str]

    @abstractmethod
    def extract_features(self, raw_input: Any) -> dict[str, Any]:
        """Reduce one raw input (a row, a document, ...) to monitorable features."""

    @abstractmethod
    def compute_baseline_stats(self, reference_data: Any) -> dict[str, Any]:
        """Summarize a reference dataset into whatever compute_drift needs later."""

    @abstractmethod
    def compute_drift(
        self, baseline_stats: dict[str, Any], window_features: list[dict[str, Any]]
    ) -> list[DriftResult]:
        """Compare a window of extracted features against the baseline."""

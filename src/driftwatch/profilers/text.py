"""Text drift: embedding centroid distance, sampled MMD, length shift, vocabulary drift.

Embedding is behind a small `Embedder` protocol so callers can inject a
custom model (or a fake one for fast, offline tests) instead of the default
`SentenceTransformerEmbedder`, which lazily imports `sentence_transformers`
(the `[text]` extra) so the base package stays torch-free.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Protocol

import numpy as np
from scipy import stats as scipy_stats
from scipy.spatial.distance import jensenshannon

from driftwatch.profilers.base import DriftResult, Profiler

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
_MAX_EMBED_SAMPLE = 500
_MAX_LENGTH_SAMPLE = 1000
_VOCAB_TOP_K = 500
_CENTROID_DRIFT_THRESHOLD = 0.1  # cosine distance
_KS_P_VALUE_THRESHOLD = 0.05
_JS_DRIFT_THRESHOLD = 0.1


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Default embedder. Requires `pip install driftwatch[text]`."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model: Any = None

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "Text modality drift needs sentence-transformers: "
                    "pip install 'driftwatch[text]'"
                ) from e
            self._model = SentenceTransformer(self._model_name)
        return np.asarray(self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False))


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _vocab_distribution(texts: list[str], top_k: int = _VOCAB_TOP_K) -> dict[str, float]:
    counter: Counter[str] = Counter()
    for t in texts:
        counter.update(_tokenize(t))
    total = sum(counter.values())
    if total == 0:
        return {}
    return {word: count / total for word, count in counter.most_common(top_k)}


def _jensen_shannon(dist_a: dict[str, float], dist_b: dict[str, float]) -> float:
    vocab = sorted(set(dist_a) | set(dist_b))
    if not vocab:
        return 0.0
    a = np.array([dist_a.get(w, 0.0) for w in vocab])
    b = np.array([dist_b.get(w, 0.0) for w in vocab])
    a_sum, b_sum = a.sum(), b.sum()
    if a_sum == 0 or b_sum == 0:
        return 1.0
    js = jensenshannon(a / a_sum, b / b_sum, base=2)
    return 0.0 if np.isnan(js) else float(js)


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denom == 0 else float(1 - np.dot(a, b) / denom)


def _rbf_mmd(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) == 0 or len(y) == 0:
        return 0.0
    gamma = 1.0 / x.shape[1]

    def kernel(u: np.ndarray, v: np.ndarray) -> np.ndarray:
        sq_dists = (
            (u**2).sum(axis=1)[:, None] + (v**2).sum(axis=1)[None, :] - 2 * u @ v.T
        )
        return np.exp(-gamma * np.clip(sq_dists, 0, None))

    xx, yy, xy = kernel(x, x), kernel(y, y), kernel(x, y)
    return float(xx.mean() + yy.mean() - 2 * xy.mean())


def _subsample(embeddings: np.ndarray, n: int) -> np.ndarray:
    if len(embeddings) <= n:
        return embeddings
    idx = np.linspace(0, len(embeddings) - 1, n).astype(int)
    return embeddings[idx]


class TextProfiler(Profiler):
    modality = "text"

    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or SentenceTransformerEmbedder()

    def extract_features(self, raw_input: Any) -> dict[str, list[Any]]:
        if isinstance(raw_input, str):
            return {"text": [raw_input]}
        if isinstance(raw_input, list) and all(isinstance(x, str) for x in raw_input):
            return {"text": list(raw_input)}
        raise TypeError(f"TextProfiler can't extract features from {type(raw_input)!r}")

    def compute_baseline_stats(self, reference_data: list[str]) -> dict[str, Any]:
        texts = list(reference_data)
        embeddings = self.embedder.embed(texts)
        centroid = embeddings.mean(axis=0)
        lengths = [len(t) for t in texts]

        return {
            "centroid": centroid.tolist(),
            "embedding_sample": _subsample(embeddings, _MAX_EMBED_SAMPLE).tolist(),
            "length_sample": lengths[:_MAX_LENGTH_SAMPLE],
            "vocab": _vocab_distribution(texts),
            "row_count": len(texts),
        }

    def compute_drift(
        self, baseline_stats: dict[str, Any], window_features: list[dict[str, Any]]
    ) -> list[DriftResult]:
        texts: list[str] = []
        for feats in window_features:
            texts.extend(feats.get("text", []))
        if not texts:
            return []

        embeddings = self.embedder.embed(texts)
        centroid = embeddings.mean(axis=0)
        baseline_centroid = np.array(baseline_stats["centroid"])
        centroid_distance = _cosine_distance(centroid, baseline_centroid)

        results = [
            DriftResult(
                metric_name="embedding_centroid_distance",
                value=centroid_distance,
                is_drifted=bool(centroid_distance > _CENTROID_DRIFT_THRESHOLD),
            )
        ]

        baseline_embed_sample = np.array(baseline_stats["embedding_sample"])
        window_sample = _subsample(embeddings, _MAX_EMBED_SAMPLE)
        if len(baseline_embed_sample) and len(window_sample):
            mmd = _rbf_mmd(baseline_embed_sample, window_sample)
            results.append(DriftResult(metric_name="mmd", value=mmd))

        lengths = [len(t) for t in texts]
        if baseline_stats["length_sample"]:
            ks_stat, ks_p = scipy_stats.ks_2samp(baseline_stats["length_sample"], lengths)
            results.append(
                DriftResult(
                    metric_name="length_ks_statistic",
                    value=float(ks_stat),
                    details={"p_value": float(ks_p)},
                    is_drifted=bool(ks_p < _KS_P_VALUE_THRESHOLD),
                )
            )

        window_vocab = _vocab_distribution(texts)
        js = _jensen_shannon(baseline_stats["vocab"], window_vocab)
        results.append(
            DriftResult(
                metric_name="vocab_js_divergence",
                value=js,
                is_drifted=bool(js > _JS_DRIFT_THRESHOLD),
            )
        )

        baseline_words = set(baseline_stats["vocab"])
        window_tokens = [tok for t in texts for tok in _tokenize(t)]
        oov_rate = (
            sum(1 for tok in window_tokens if tok not in baseline_words) / len(window_tokens)
            if window_tokens
            else 0.0
        )
        results.append(DriftResult(metric_name="oov_rate", value=oov_rate))

        return results

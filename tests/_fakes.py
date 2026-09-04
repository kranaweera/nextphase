"""Deterministic, offline stand-ins for real ML dependencies used in tests."""

from __future__ import annotations

import re
import zlib

import numpy as np

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


class FakeEmbedder:
    """A hashed bag-of-words 'embedder' — no network, no model download.

    Good enough to make semantically-similar texts cluster and semantically
    different texts separate, which is all TextProfiler's drift tests need.
    """

    def __init__(self, dim: int = 32):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim))
        for i, text in enumerate(texts):
            for token in _TOKEN_RE.findall(text.lower()):
                vectors[i, zlib.crc32(token.encode("utf-8")) % self.dim] += 1
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return vectors / norms

"""Embedding models.

* `sentence_transformers` (default when installed): all-MiniLM-L6-v2, runs locally, free.
* `hash`: a dependency-free hashed bag-of-words embedder used as an offline fallback
  and in unit tests. Much weaker semantically, but deterministic.
"""
from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import Optional

from .config import settings
from . import textutils as tu

log = logging.getLogger("crag.embeddings")


class HashEmbedder:
    name = "hash-768"

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def _idx(self, feat: str) -> tuple[int, float]:
        h = int(hashlib.md5(feat.encode()).hexdigest(), 16)
        return h % self.dim, (1.0 if (h >> 64) & 1 else -1.0)

    def _embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = tu.tokens(text)
        feats: list[tuple[str, float]] = [(t, 1.0) for t in toks]
        feats += [(f"{a}_{b}", 0.5) for a, b in zip(toks, toks[1:])]
        for t in toks:
            if len(t) > 4:
                feats += [(f"#{t[i:i + 4]}", 0.25) for i in range(len(t) - 3)]
        for f, w in feats:
            i, sign = self._idx(f)
            v[i] += sign * w
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class STEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.name = model_name.split("/")[-1]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()


_embedder = None


_lock = threading.Lock()


def get_embedder():
    with _lock:
        return _get_embedder()


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    backend = settings.embedding_backend
    if backend in ("auto", "sentence_transformers"):
        try:
            _embedder = STEmbedder(settings.embedding_model)
            log.info("Using sentence-transformers embeddings: %s", settings.embedding_model)
            return _embedder
        except Exception as e:  # not installed / no internet for first download
            if backend == "sentence_transformers":
                raise
            log.warning("sentence-transformers unavailable (%s) -> falling back to hash embeddings", e)
    _embedder = HashEmbedder()
    return _embedder


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def reset_embedder(e: Optional[object] = None) -> None:
    """Used by tests to inject a specific embedder."""
    global _embedder
    _embedder = e

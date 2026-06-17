"""Embedding functions for the pgvector memory backend.

Two implementations behind one callable interface ``embed(text) -> list[float]``:

* :class:`OpenAICompatibleEmbeddings` — real semantic embeddings from an
  OpenAI-compatible endpoint (OpenAI directly, or ECHO once it proxies the
  embeddings route). Use this in production.
* :class:`HashingEmbeddings` — a deterministic, dependency-free fallback that
  hashes tokens into a fixed-width vector. Not semantic, but needs no API key
  and is reproducible — handy for local dev and offline tests.

:func:`build_embeddings_from_env` picks one based on environment variables.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol

_WORD = re.compile(r"[a-z0-9]+")


class EmbeddingFunction(Protocol):
    dimensions: int

    def __call__(self, text: str) -> list[float]: ...


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class HashingEmbeddings:
    """Deterministic bag-of-words hashing embedding (no network, no deps)."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def __call__(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in _WORD.findall((text or "").lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign
        return _l2_normalize(vec)


class OpenAICompatibleEmbeddings:
    """Embeddings from an OpenAI-compatible API (OpenAI or ECHO)."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int = 1536,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._base_url = base_url
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: only needed for this backend

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def __call__(self, text: str) -> list[float]:
        client = self._ensure_client()
        resp = client.embeddings.create(model=self.model, input=text or "")
        return list(resp.data[0].embedding)


def build_embeddings_from_env() -> EmbeddingFunction:
    """Choose an embedding function from the environment.

    EMBEDDINGS_PROVIDER=openai  -> OpenAICompatibleEmbeddings
                       =hashing -> HashingEmbeddings (default)
    """
    provider = os.getenv("EMBEDDINGS_PROVIDER", "hashing").lower()
    if provider == "openai":
        return OpenAICompatibleEmbeddings(
            model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"),
            api_key=os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("EMBEDDINGS_BASE_URL"),
            dimensions=int(os.getenv("EMBEDDINGS_DIM", "1536")),
        )
    return HashingEmbeddings(dimensions=int(os.getenv("EMBEDDINGS_DIM", "384")))

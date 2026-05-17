"""Embedding service — generate and cache text embeddings.

``EmbeddingService`` wraps :class:`~app.providers.resilient.ResilientAIService`
to produce embedding vectors and caches results in Redis so that identical
(text, model) pairs never trigger a second API call.

Cache-key design
----------------
``make_key("embedding", model, sha256_hex(text))``

The SHA-256 of the raw text (not the text itself) is passed as the *parts*
argument so that long inputs do not produce unwieldy keys.  The model name
is included so that a model change automatically invalidates cached vectors.

Batch behaviour
---------------
:meth:`embed_many` looks up every text individually in the cache, collects
the misses, calls the AI provider *once* for all of them, caches each
result, and assembles the full list in original order.  This minimises
round-trips to both Redis and the embedding API.

TTL
---
Embeddings are deterministic for a fixed (text, model) pair and do not
expire naturally, so they are cached for 24 hours — long enough that a
restarted service reuses warm cache, short enough that rotating to a new
model version self-heals overnight.
"""

from __future__ import annotations

import hashlib

from app.core.logging import get_logger
from app.infrastructure.cache import Cache
from app.infrastructure.keys import make_key
from app.providers.resilient import ResilientAIService

log = get_logger(__name__)

_EMBEDDING_TTL_SECONDS = 86_400  # 24 hours


class EmbeddingService:
    """Generate and cache text embeddings.

    Parameters
    ----------
    ai_service:
        Resilient multi-provider AI service used when a cache miss occurs.
    cache:
        Redis-backed cache (may be a no-op when Redis is unavailable).
    model:
        Embedding model name used as part of the cache key so that
        switching models does not serve stale vectors.
    """

    def __init__(
        self,
        *,
        ai_service: ResilientAIService,
        cache: Cache,
        model: str,
    ) -> None:
        self._ai_service = ai_service
        self._cache = cache
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_one(self, text: str) -> list[float]:
        """Return the embedding vector for a single text string.

        Checks the cache first; calls the AI provider on a miss and stores
        the result before returning.

        Parameters
        ----------
        text:
            The string to embed.  Should be non-empty.

        Returns
        -------
        list[float]
            The embedding vector produced by the configured model.
        """
        key = self._make_cache_key(text)
        cached: list[float] | None = await self._cache.get(key)
        if cached is not None:
            log.debug("embedding.cache_hit", model=self._model)
            return cached

        log.debug("embedding.cache_miss", model=self._model)
        vectors = await self._ai_service.embed(text)
        vector = vectors[0]
        await self._cache.set(key, vector, ttl=_EMBEDDING_TTL_SECONDS)
        return vector

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a list of texts.

        Resolves each text against the cache individually, then batches all
        cache misses into a single call to the AI provider, caches each new
        vector, and returns the full list in the original input order.

        Parameters
        ----------
        texts:
            List of strings to embed.  May be empty (returns ``[]``).

        Returns
        -------
        list[list[float]]
            Embedding vectors in the same order as *texts*.
        """
        if not texts:
            return []

        keys = [self._make_cache_key(t) for t in texts]
        cached_results: list[list[float] | None] = [await self._cache.get(k) for k in keys]

        # Collect indices and texts for cache misses.
        miss_indices: list[int] = []
        miss_texts: list[str] = []
        for i, result in enumerate(cached_results):
            if result is None:
                miss_indices.append(i)
                miss_texts.append(texts[i])

        hits = len(texts) - len(miss_indices)
        log.debug(
            "embedding.batch",
            total=len(texts),
            cache_hits=hits,
            api_calls=len(miss_indices),
            model=self._model,
        )

        if miss_texts:
            # Single batched API call for all misses.
            new_vectors = await self._ai_service.embed(miss_texts)
            for idx, vector in zip(miss_indices, new_vectors, strict=False):
                cached_results[idx] = vector
                await self._cache.set(keys[idx], vector, ttl=_EMBEDDING_TTL_SECONDS)

        # All slots are now populated; the cast is safe.
        return cached_results  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_cache_key(self, text: str) -> str:
        """Build a deterministic cache key for the given text.

        The text is hashed with SHA-256 before inclusion so that long
        inputs do not bloat the key.  The model name is part of the key
        so that changing the embedding model automatically invalidates
        cached vectors.
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return make_key("embedding", self._model, text_hash)

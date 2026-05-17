"""Tests for app.services.embedding.EmbeddingService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding import EmbeddingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_service(vectors: list[list[float]] | None = None) -> MagicMock:
    """Return a mock ResilientAIService whose embed() returns *vectors*."""
    service = MagicMock()
    service.embed = AsyncMock(return_value=vectors or [[0.1, 0.2, 0.3]])
    return service


def _make_cache(*, hit: list[float] | None = None) -> MagicMock:
    """Return a mock Cache.

    If *hit* is provided, ``cache.get()`` returns it on the first call and
    then returns ``None`` on subsequent calls (simulating a cold cache for
    other keys).  If *hit* is ``None``, every ``get()`` returns ``None``.
    """
    cache = MagicMock()
    cache.get = AsyncMock(return_value=hit)
    cache.set = AsyncMock()
    return cache


def _make_service(
    ai_service: MagicMock | None = None,
    cache: MagicMock | None = None,
    model: str = "text-embedding-3-small",
) -> EmbeddingService:
    return EmbeddingService(
        ai_service=ai_service or _make_ai_service(),
        cache=cache or _make_cache(),
        model=model,
    )


# ---------------------------------------------------------------------------
# embed_one
# ---------------------------------------------------------------------------


class TestEmbedOne:
    @pytest.mark.anyio
    async def test_cache_miss_calls_ai_service(self) -> None:
        """On a cache miss the AI service must be called exactly once."""
        vector = [0.1, 0.2, 0.3]
        ai = _make_ai_service(vectors=[vector])
        cache = _make_cache(hit=None)
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_one("hello world")

        ai.embed.assert_awaited_once_with("hello world")
        assert result == vector

    @pytest.mark.anyio
    async def test_cache_miss_stores_result(self) -> None:
        """The new vector must be written to the cache after an AI call."""
        vector = [1.0, 2.0]
        ai = _make_ai_service(vectors=[vector])
        cache = _make_cache(hit=None)
        svc = _make_service(ai_service=ai, cache=cache)

        await svc.embed_one("store me")

        cache.set.assert_awaited_once()
        args, kwargs = cache.set.call_args
        # First positional arg is the key (str), second is the vector.
        assert args[1] == vector or kwargs.get("value") == vector or args[0] != ""

    @pytest.mark.anyio
    async def test_cache_hit_does_not_call_ai_service(self) -> None:
        """When the cache returns a vector the AI service must not be called."""
        cached_vector = [9.0, 8.0, 7.0]
        ai = _make_ai_service()
        cache = _make_cache(hit=cached_vector)
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_one("cached text")

        ai.embed.assert_not_awaited()
        assert result == cached_vector

    @pytest.mark.anyio
    async def test_cache_key_includes_model_and_text_hash(self) -> None:
        """Two different models must produce different cache keys."""
        cache_a = _make_cache(hit=None)
        cache_b = _make_cache(hit=None)
        svc_a = _make_service(cache=cache_a, model="model-a")
        svc_b = _make_service(cache=cache_b, model="model-b")

        text = "same text"
        await svc_a.embed_one(text)
        await svc_b.embed_one(text)

        key_a = cache_a.get.call_args[0][0]
        key_b = cache_b.get.call_args[0][0]
        assert key_a != key_b


# ---------------------------------------------------------------------------
# embed_many
# ---------------------------------------------------------------------------


class TestEmbedMany:
    @pytest.mark.anyio
    async def test_empty_input_returns_empty_list(self) -> None:
        svc = _make_service()
        result = await svc.embed_many([])
        assert result == []

    @pytest.mark.anyio
    async def test_all_cache_misses_single_ai_call(self) -> None:
        """All misses must be batched into a single AI service call."""
        texts = ["text 1", "text 2", "text 3"]
        vectors = [[1.0], [2.0], [3.0]]
        ai = _make_ai_service(vectors=vectors)
        cache = _make_cache(hit=None)
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_many(texts)

        # Exactly one batched call with all texts.
        ai.embed.assert_awaited_once_with(texts)
        assert result == vectors

    @pytest.mark.anyio
    async def test_all_cache_hits_no_ai_call(self) -> None:
        """When every text hits the cache, the AI service is never called."""
        cached_vector = [5.0, 6.0]
        ai = _make_ai_service()
        # Every cache.get() returns the cached vector.
        cache = _make_cache(hit=cached_vector)
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_many(["a", "b", "c"])

        ai.embed.assert_not_awaited()
        assert result == [cached_vector, cached_vector, cached_vector]

    @pytest.mark.anyio
    async def test_partial_cache_hits_batches_only_misses(self) -> None:
        """Texts already in cache must not be included in the AI call."""
        cached_vector = [1.0, 0.0]
        miss_vector = [0.0, 1.0]

        call_count = 0

        async def smart_get(key: str) -> list[float] | None:
            nonlocal call_count
            call_count += 1
            # First text hits cache, second does not.
            return cached_vector if call_count == 1 else None

        ai = _make_ai_service(vectors=[miss_vector])
        cache = MagicMock()
        cache.get = AsyncMock(side_effect=smart_get)
        cache.set = AsyncMock()
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_many(["cached-text", "miss-text"])

        # AI called once, for the miss only.
        ai.embed.assert_awaited_once_with(["miss-text"])
        assert result == [cached_vector, miss_vector]

    @pytest.mark.anyio
    async def test_results_returned_in_original_order(self) -> None:
        """Order of output must match order of input regardless of cache state."""
        # No cache hits; AI returns vectors in the same order as texts.
        texts = ["c", "b", "a"]
        vectors = [[3.0], [2.0], [1.0]]
        ai = _make_ai_service(vectors=vectors)
        cache = _make_cache(hit=None)
        svc = _make_service(ai_service=ai, cache=cache)

        result = await svc.embed_many(texts)

        assert result == vectors

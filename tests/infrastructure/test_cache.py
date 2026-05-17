"""Tests for app.infrastructure.cache.Cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from redis.exceptions import ConnectionError as RedisConnectionError, RedisError

from app.infrastructure.cache import Cache
from app.infrastructure.keys import make_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(ttl: int = 3600, enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.redis_url = "redis://localhost:6379/0"
    s.cache_default_ttl_seconds = ttl
    s.cache_enabled = enabled
    return s


def _make_cache(*, ttl: int = 3600, redis_client: MagicMock | None = None) -> Cache:
    """Return a Cache with an injected mock Redis client."""
    mock_redis = redis_client or MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.ping = AsyncMock(return_value=True)
    return Cache(settings=_make_settings(ttl=ttl), client=mock_redis)


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestCacheGet:
    async def test_returns_none_on_cache_miss(self) -> None:
        cache = _make_cache()
        cache._client.get = AsyncMock(return_value=None)
        assert await cache.get("missing-key") is None

    async def test_returns_deserialised_value_on_hit(self) -> None:
        import orjson

        cache = _make_cache()
        payload = {"answer": "hello", "score": 0.9}
        cache._client.get = AsyncMock(return_value=orjson.dumps(payload))
        result = await cache.get("my-key")
        assert result == payload

    async def test_returns_none_on_redis_error(self) -> None:
        """Redis errors must be swallowed and return None."""
        cache = _make_cache()
        cache._client.get = AsyncMock(side_effect=RedisConnectionError("no server"))
        # Must not raise
        result = await cache.get("key")
        assert result is None

    async def test_redis_error_logged_as_warning(self) -> None:
        import structlog.testing

        cache = _make_cache()
        cache._client.get = AsyncMock(side_effect=RedisError("boom"))
        with structlog.testing.capture_logs() as logs:
            await cache.get("k")
        warnings = [entry for entry in logs if entry.get("log_level") == "warning"]
        assert any("cache.get.error" in str(entry) for entry in warnings)

    async def test_returns_none_when_client_is_none(self) -> None:
        """When cache is disabled, get() always returns None."""
        cache = Cache(settings=_make_settings(enabled=False))
        assert await cache.get("any-key") is None


# ---------------------------------------------------------------------------
# set()
# ---------------------------------------------------------------------------


class TestCacheSet:
    async def test_stores_value_with_default_ttl(self) -> None:
        cache = _make_cache(ttl=60)
        await cache.set("k", {"x": 1})
        cache._client.set.assert_awaited_once()
        call_kwargs = cache._client.set.call_args
        assert call_kwargs.kwargs.get("ex") == 60 or (
            len(call_kwargs.args) >= 2 and call_kwargs.kwargs.get("ex") == 60
        )

    async def test_stores_value_with_explicit_ttl(self) -> None:
        cache = _make_cache(ttl=60)
        await cache.set("k", "val", ttl=300)
        call_kwargs = cache._client.set.call_args
        # ttl=300 overrides the default 60
        assert call_kwargs.kwargs.get("ex") == 300

    async def test_no_expiry_when_ttl_zero(self) -> None:
        cache = _make_cache(ttl=60)
        await cache.set("k", "val", ttl=0)
        call_kwargs = cache._client.set.call_args
        assert call_kwargs.kwargs.get("ex") is None

    async def test_swallows_redis_error(self) -> None:
        cache = _make_cache()
        cache._client.set = AsyncMock(side_effect=RedisError("disk full"))
        # Must not raise
        await cache.set("k", "v")

    async def test_redis_error_logged_as_warning(self) -> None:
        import structlog.testing

        cache = _make_cache()
        cache._client.set = AsyncMock(side_effect=RedisError("disk full"))
        with structlog.testing.capture_logs() as logs:
            await cache.set("k", "v")
        warnings = [entry for entry in logs if entry.get("log_level") == "warning"]
        assert any("cache.set.error" in str(entry) for entry in warnings)

    async def test_no_op_when_client_is_none(self) -> None:
        cache = Cache(settings=_make_settings(enabled=False))
        await cache.set("k", "v")  # must not raise


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


class TestCacheDelete:
    async def test_calls_redis_delete(self) -> None:
        cache = _make_cache()
        await cache.delete("my-key")
        cache._client.delete.assert_awaited_once_with("my-key")

    async def test_swallows_redis_error(self) -> None:
        cache = _make_cache()
        cache._client.delete = AsyncMock(side_effect=RedisError("gone"))
        await cache.delete("k")  # must not raise


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


class TestCachePing:
    async def test_returns_true_when_redis_responds(self) -> None:
        cache = _make_cache()
        cache._client.ping = AsyncMock(return_value=True)
        assert await cache.ping() is True

    async def test_returns_false_on_connection_error(self) -> None:
        cache = _make_cache()
        cache._client.ping = AsyncMock(side_effect=RedisConnectionError("down"))
        assert await cache.ping() is False

    async def test_returns_false_when_client_is_none(self) -> None:
        cache = Cache(settings=_make_settings(enabled=False))
        assert await cache.ping() is False


# ---------------------------------------------------------------------------
# make_key()
# ---------------------------------------------------------------------------


class TestCacheMakeKey:
    def test_delegates_to_keys_module(self) -> None:
        """Cache.make_key must produce the same key as keys.make_key."""
        expected = make_key("rag", "model", "hash")
        assert Cache.make_key("rag", "model", "hash") == expected

    def test_same_inputs_deterministic(self) -> None:
        k1 = Cache.make_key("rag", "gpt-4o-mini", "q123")
        k2 = Cache.make_key("rag", "gpt-4o-mini", "q123")
        assert k1 == k2

    def test_version_override(self) -> None:
        k = Cache.make_key("rag", "x", version="v2")
        assert k.startswith("v2:rag:")

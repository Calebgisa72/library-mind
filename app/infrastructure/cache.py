"""Redis-backed response cache with graceful no-op fallback.

Every operation is wrapped in a broad ``redis.RedisError`` catch.  When Redis
is unreachable the application continues to function -- queries are simply
answered without caching.  This satisfies Part 2 acceptance criterion:
"The application starts and runs correctly even when Redis is not running."

Usage::

    cache = Cache(settings=get_settings())
    key   = cache.make_key("rag", model, question_hash)
    hit   = await cache.get(key)
    if hit is None:
        result = await expensive_ai_call()
        await cache.set(key, result, ttl=3600)

All values are serialised with ``orjson`` so complex types (dicts, lists,
dataclasses serialised to dicts) round-trip cleanly.

Cache-key versioning
--------------------
Bump the ``version`` argument to ``make_key`` (or the module-level default
``"v1"``) whenever a prompt template or response shape changes.  This
invalidates stale entries for that scope without touching the rest of the
namespace -- a cheap alternative to ``FLUSHDB``.
"""

from __future__ import annotations

from typing import Any

import orjson
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.settings import Settings
from app.infrastructure.keys import make_key as _make_key

log = get_logger(__name__)


class Cache:
    """Async Redis cache with graceful fallback to a no-op when unavailable.

    Parameters
    ----------
    settings:
        Application settings supplying ``redis_url``, ``cache_enabled``,
        and ``cache_default_ttl_seconds``.
    client:
        Optional pre-constructed ``redis.asyncio.Redis`` instance.  Pass
        one in tests to avoid a real Redis connection.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        client: aioredis.Redis | None = None,  # type: ignore[type-arg]
    ) -> None:
        self._settings = settings
        # Lazily connected: constructing the client does not open a socket.
        if client is not None:
            self._client: aioredis.Redis | None = client  # type: ignore[type-arg]
        elif settings.cache_enabled:
            self._client = aioredis.Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=False,  # we handle encoding ourselves
            )
        else:
            # cache_enabled=False in settings: behave as if Redis is always down.
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or ``None`` on miss or error.

        Deserialises the stored bytes with ``orjson``.  Returns ``None`` when:
        * the key does not exist in Redis;
        * Redis is unreachable (logs WARNING, does not raise);
        * caching is disabled.
        """
        if self._client is None:
            return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            return orjson.loads(raw)
        except RedisError as exc:
            log.warning("cache.get.error", key=key, error=str(exc))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | None = None,
    ) -> None:
        """Store *value* under *key* in Redis.

        Parameters
        ----------
        key:
            Cache key (usually produced by :meth:`make_key`).
        value:
            Any ``orjson``-serialisable object.
        ttl:
            Time-to-live in seconds.  Falls back to
            ``settings.cache_default_ttl_seconds`` when omitted.
            Pass ``0`` to store without expiry.

        Silently no-ops when Redis is unreachable (logs WARNING).
        """
        if self._client is None:
            return
        effective_ttl = ttl if ttl is not None else self._settings.cache_default_ttl_seconds
        try:
            raw = orjson.dumps(value)
            if effective_ttl > 0:
                await self._client.set(key, raw, ex=effective_ttl)
            else:
                await self._client.set(key, raw)
        except RedisError as exc:
            log.warning("cache.set.error", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Delete *key* from Redis.  Silently no-ops on error."""
        if self._client is None:
            return
        try:
            await self._client.delete(key)
        except RedisError as exc:
            log.warning("cache.delete.error", key=key, error=str(exc))

    async def ping(self) -> bool:
        """Return ``True`` if Redis is reachable, ``False`` otherwise.

        Used by the ``/health`` endpoint.  Never raises.
        """
        if self._client is None:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Key construction (delegated to keys module for testability)
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(scope: str, *parts: Any, version: str = "v1") -> str:
        """Build a versioned, deterministic cache key.

        Delegates to :func:`app.infrastructure.keys.make_key`.  Exposed here
        so callers do not need to import from two modules.

        Returns a key in the form ``"{version}:{scope}:{sha256_hex}"``.
        """
        return _make_key(scope, *parts, version=version)

"""Infrastructure layer -- shared cross-cutting concerns.

Phase 2 public surface:

* :class:`~app.infrastructure.cache.Cache` -- async Redis cache with
  graceful no-op fallback.
* :func:`~app.infrastructure.keys.make_key` -- deterministic cache-key
  builder (also available as ``Cache.make_key``).
* :class:`~app.infrastructure.rate_limiter.TokenBucketRateLimiter` --
  asyncio token-bucket rate limiter.
* :class:`~app.infrastructure.usage_tracker.UsageTracker` -- in-memory
  token count and USD cost accumulator.
* :class:`~app.infrastructure.usage_tracker.UsageRecord` -- immutable
  per-call usage snapshot.
* :data:`~app.infrastructure.usage_tracker.PRICING` -- model price table.

Phase 3 will add:

* :class:`~app.infrastructure.vector_store.VectorStore` -- ChromaDB wrapper.
"""

from app.infrastructure.cache import Cache
from app.infrastructure.keys import make_key
from app.infrastructure.rate_limiter import TokenBucketRateLimiter
from app.infrastructure.usage_tracker import PRICING, UsageRecord, UsageTracker

__all__ = [
    "Cache",
    "PRICING",
    "TokenBucketRateLimiter",
    "UsageRecord",
    "UsageTracker",
    "make_key",
]

"""Infrastructure layer — shared cross-cutting concerns.

Components:

* :mod:`app.infrastructure.cache` — Redis-backed cache with graceful
  fallback to a no-op when Redis is unavailable (Part 2).
* :mod:`app.infrastructure.rate_limiter` — thread-safe token bucket (Part 2).
* :mod:`app.infrastructure.usage_tracker` — token counting + cost
  estimation per AI call (Part 2).
* :mod:`app.infrastructure.vector_store` — ChromaDB wrapper for the
  semantic catalogue (Part 3).
"""

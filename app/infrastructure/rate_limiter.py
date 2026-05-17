"""Asyncio-native token-bucket rate limiter.

Implements the token-bucket algorithm: a bucket starts full (capacity =
``burst``) and refills at ``requests_per_minute / 60`` tokens per second.
Each :meth:`acquire` call removes one token; when the bucket is empty it
raises :class:`~app.core.exceptions.RateLimitExceededError`.

Why asyncio.Lock?
-----------------
FastAPI runs all request handlers concurrently in a single asyncio event loop.
``asyncio.Lock`` prevents two coroutines from refilling and consuming tokens
simultaneously.  It is cheaper than ``threading.Lock`` in an async context
and sufficient because there is only one event loop thread.

Thread-safety note
------------------
``asyncio.Lock`` is *not* safe across multiple OS threads.  If the application
ever moves to a multi-threaded deployment (e.g. Gunicorn with multiple async
workers in the same process), replace with a Redis-backed distributed limiter
or a ``threading.Lock`` + ``asyncio.run_in_executor`` pattern.  For the lab's
single-process, single-event-loop deployment this is the correct choice.

Usage::

    limiter = TokenBucketRateLimiter(
        requests_per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
    )
    await limiter.acquire()   # raises RateLimitExceededError if empty
"""

from __future__ import annotations

import asyncio
import time

from app.core.exceptions import RateLimitExceededError
from app.core.logging import get_logger

log = get_logger(__name__)


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Parameters
    ----------
    requests_per_minute:
        Sustained refill rate.  For example, ``60`` means one token per
        second.  Read from ``Settings.rate_limit_per_minute``.
    burst:
        Maximum bucket capacity (and initial token count).  Allows short
        bursts above the sustained rate without immediate rejection.
        Read from ``Settings.rate_limit_burst``.
    """

    def __init__(self, requests_per_minute: int, burst: int) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")
        self._rate: float = requests_per_minute / 60.0  # tokens per second
        self._burst: float = float(burst)
        self._tokens: float = float(burst)   # start full
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire one token, blocking briefly for the lock but not for refill.

        Raises
        ------
        RateLimitExceededError
            When the bucket has fewer than one token available after the
            current-time refill.

        Notes
        -----
        The refill is computed from elapsed wall-clock time (``time.monotonic``)
        so callers never need to sleep -- they either get a token immediately or
        are rejected immediately.  There is no queuing.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                log.debug(
                    "rate_limiter.acquired",
                    tokens_remaining=round(self._tokens, 2),
                )
            else:
                log.warning(
                    "rate_limiter.rejected",
                    tokens_available=round(self._tokens, 3),
                )
                raise RateLimitExceededError(
                    "Rate limit exceeded. Too many requests -- please slow down."
                )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens proportional to elapsed time since last refill.

        Called inside the lock so it is safe against concurrent coroutines.
        Tokens are clamped at ``_burst`` to prevent the bucket from
        growing beyond capacity.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    @property
    def tokens(self) -> float:
        """Current token count (approximate -- not lock-protected).

        Intended only for testing and health checks; do not use for
        admission control.
        """
        return self._tokens

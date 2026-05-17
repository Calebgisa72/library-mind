"""Tests for app.infrastructure.rate_limiter.TokenBucketRateLimiter."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from app.core.exceptions import RateLimitExceededError
from app.infrastructure.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    # ------------------------------------------------------------------
    # Happy-path: tokens available
    # ------------------------------------------------------------------

    async def test_acquire_succeeds_when_bucket_has_tokens(self) -> None:
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=10)
        # Bucket starts full -- first 10 acquires must all succeed.
        for _ in range(10):
            await limiter.acquire()

    async def test_acquire_returns_none_on_success(self) -> None:
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=5)
        result = await limiter.acquire()
        assert result is None

    # ------------------------------------------------------------------
    # Bucket exhaustion
    # ------------------------------------------------------------------

    async def test_raises_when_bucket_is_empty(self) -> None:
        """The (burst+1)th call must raise RateLimitExceededError."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=3)
        for _ in range(3):
            await limiter.acquire()
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire()

    async def test_rate_limit_exceeded_is_correct_type(self) -> None:
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=1)
        await limiter.acquire()
        exc = None
        try:
            await limiter.acquire()
        except RateLimitExceededError as e:
            exc = e
        assert exc is not None, "Expected RateLimitExceededError was not raised"

    async def test_excess_requests_trigger_rate_limit_error(self) -> None:
        """Simulate the lab scenario: 61 requests within a minute triggers 429."""
        # Use burst=60 and rate=60/min; all 60 fit in the burst window.
        # The 61st must fail (no wall-clock time has elapsed to refill).
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=60)
        for _ in range(60):
            await limiter.acquire()
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire()

    # ------------------------------------------------------------------
    # Refill behaviour
    # ------------------------------------------------------------------

    async def test_tokens_refill_after_elapsed_time(self) -> None:
        """After 1 second the bucket refills by rate tokens/sec."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=5)
        # Drain the bucket completely.
        for _ in range(5):
            await limiter.acquire()

        # Simulate 2 seconds elapsing by advancing _last_refill 2s into the past.
        limiter._last_refill -= 2.0  # rate=1 tok/sec -> +2 tokens refilled

        # Now we should be able to acquire 2 more tokens.
        await limiter.acquire()
        await limiter.acquire()

        # But not a third (only 2 tokens were refilled).
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire()

    async def test_tokens_clamped_at_burst_capacity(self) -> None:
        """Even after a long idle period, tokens never exceed burst."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=5)
        # Simulate 1 hour elapsed -- without clamping tokens would be 3600.
        limiter._last_refill -= 3600.0
        limiter._refill()
        assert limiter.tokens <= 5.0

    # ------------------------------------------------------------------
    # Concurrency
    # ------------------------------------------------------------------

    async def test_concurrent_acquires_respect_burst_limit(self) -> None:
        """Concurrent coroutines must not together acquire more than burst tokens."""
        burst = 5
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst=burst)
        successes = 0
        failures = 0

        async def attempt() -> None:
            nonlocal successes, failures
            try:
                await limiter.acquire()
                successes += 1
            except RateLimitExceededError:
                failures += 1

        await asyncio.gather(*[attempt() for _ in range(burst + 3)])
        assert successes == burst
        assert failures == 3

    # ------------------------------------------------------------------
    # Constructor validation
    # ------------------------------------------------------------------

    def test_raises_on_zero_rate(self) -> None:
        with pytest.raises(ValueError, match="requests_per_minute"):
            TokenBucketRateLimiter(requests_per_minute=0, burst=5)

    def test_raises_on_zero_burst(self) -> None:
        with pytest.raises(ValueError, match="burst"):
            TokenBucketRateLimiter(requests_per_minute=60, burst=0)

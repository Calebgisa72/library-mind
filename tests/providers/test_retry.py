"""Tests for app.providers.retry — build_provider_retry factory."""

from __future__ import annotations

import pytest
from tenacity import stop_after_attempt, wait_none

from app.providers.retry import build_provider_retry


class _Boom(Exception):
    """Synthetic transient error used only in these tests."""


class _Permanent(Exception):
    """Synthetic non-transient error — should never be retried."""


class TestBuildProviderRetry:
    async def test_succeeds_on_first_attempt(self) -> None:
        """No retry needed when the decorated function succeeds immediately."""
        call_count = 0

        @build_provider_retry((_Boom,), stop=stop_after_attempt(3), wait=wait_none())
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 1

    async def test_retries_on_transient_error(self) -> None:
        """Decorated function is retried when it raises a transient error."""
        call_count = 0

        @build_provider_retry((_Boom,), stop=stop_after_attempt(3), wait=wait_none())
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _Boom("transient")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 3

    async def test_reraises_after_max_attempts(self) -> None:
        """After exhausting all attempts, the last exception is re-raised."""

        @build_provider_retry((_Boom,), stop=stop_after_attempt(2), wait=wait_none())
        async def fn() -> str:
            raise _Boom("always fails")

        with pytest.raises(_Boom, match="always fails"):
            await fn()

    async def test_does_not_retry_non_transient_error(self) -> None:
        """Errors NOT in the transient tuple propagate without retrying."""
        call_count = 0

        @build_provider_retry((_Boom,), stop=stop_after_attempt(3), wait=wait_none())
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise _Permanent("bad request")

        with pytest.raises(_Permanent):
            await fn()

        # Must not retry a non-transient error.
        assert call_count == 1

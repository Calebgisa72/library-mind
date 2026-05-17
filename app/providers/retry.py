"""Shared tenacity retry policy for AI providers.

Each provider supplies its own tuple of transient exception types -- the
errors worth retrying (rate limits, timeouts, network hiccups). Non-transient
errors (invalid API key, bad request) propagate immediately.

Usage::

    _TRANSIENT = (openai.RateLimitError, openai.APITimeoutError, ...)

    @build_provider_retry(_TRANSIENT)
    async def _do_generate(self, ...):
        ...

Observable retries
------------------
``before_sleep=before_sleep_log(...)`` logs a WARNING through the stdlib
logger before every sleep, satisfying Part 1 acceptance criterion:
"Retry logic is observable in logs."
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.retry import RetryBaseT
from tenacity.stop import StopBaseT
from tenacity.wait import WaitBaseT

# stdlib logger that tenacity writes to; configure_logging() routes
# stdlib through structlog so these lines appear in structured output.
_log = logging.getLogger("app.providers.retry")

# Preserve the decorated function signature for type checkers.
_F = TypeVar("_F", bound=Callable[..., Any])


def build_provider_retry(
    transient_errors: tuple[type[BaseException], ...],
    *,
    stop: StopBaseT | None = None,
    wait: WaitBaseT | None = None,
    retry_condition: RetryBaseT | None = None,
) -> Callable[[_F], _F]:
    """Return a tenacity @retry decorator configured for AI provider calls.

    Parameters
    ----------
    transient_errors:
        Exception types that trigger a retry. Everything else propagates.
    stop:
        Override the default stop_after_attempt(3). Useful in tests.
    wait:
        Override the default wait_exponential(min=2, max=30). Useful in tests.
    retry_condition:
        Override the retry_if_exception_type condition.
    """
    return retry(  # type: ignore[return-value]
        stop=stop or stop_after_attempt(3),
        wait=wait or wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_condition or retry_if_exception_type(transient_errors),
        reraise=True,
        before_sleep=before_sleep_log(_log, logging.WARNING),
    )

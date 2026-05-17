"""Structured logging configuration.

We use ``structlog`` because:

* JSON output is essential for log aggregation in production.
* Context binding (``logger.bind(request_id=..., user_id=...)``) gives
  every log line the breadcrumbs needed to trace a request end-to-end.
* In development, a colourised console renderer is far friendlier than
  JSON walls of text.

Call :func:`configure_logging` exactly once, at application startup.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure stdlib logging + structlog with a shared processor chain.

    Args:
        level: Minimum log level (DEBUG/INFO/WARNING/ERROR).
        fmt: ``"json"`` for production, ``"console"`` for local dev.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors run on every record regardless of renderer.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: structlog.types.Processor
    if fmt == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route the stdlib root logger through the same handler so libraries
    # that use logging.getLogger() share our output stream/format.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # Silence overly chatty third-party loggers by default.
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger.

    Prefer module-level::

        log = get_logger(__name__)

    over ad-hoc ``structlog.get_logger()`` calls so module names appear
    in log output consistently.
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return cast(structlog.stdlib.BoundLogger, logger)

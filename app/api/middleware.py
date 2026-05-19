"""Request-ID middleware and global exception handler registration.

The middleware generates a UUID4 for every incoming request, binds it to
the structlog context so every log line emitted during that request carries
the same ``request_id``, and returns it in the ``X-Request-ID`` response
header so clients can correlate logs with their own traces.

Exception handlers are registered in ``app.main.create_app`` using the
``register_exception_handlers`` helper exported here.  Registration order
matters: FastAPI matches the *most specific* registered type first, so
narrower exceptions (``AllProvidersFailedError``, ``RateLimitExceededError``)
must be registered before their base classes (``ProviderError``,
``LibraryMindError``).
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.exceptions import (
    AllProvidersFailedError,
    LibraryMindError,
    ProviderError,
    RateLimitExceededError,
)

log = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a UUID request-ID to every request and response.

    The ID is bound to the structlog context so all log lines emitted
    during the request lifecycle carry ``request_id`` without any manual
    threading.  The same value is echoed in the ``X-Request-ID`` header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers["X-Request-ID"] = request_id
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Wire global exception handlers onto *app*.

    Registration order is narrower-first so FastAPI matches the most
    specific handler.  All handlers return ``{"detail": str(exc)}`` to
    match FastAPI's default ``HTTPException`` envelope.
    """

    @app.exception_handler(RateLimitExceededError)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
        log.warning("rate_limit.exceeded", detail=str(exc))
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(AllProvidersFailedError)
    async def _all_providers_handler(
        request: Request, exc: AllProvidersFailedError
    ) -> JSONResponse:
        log.error("providers.all_failed", detail=str(exc))
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def _provider_handler(request: Request, exc: ProviderError) -> JSONResponse:
        log.error("provider.error", detail=str(exc))
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LibraryMindError)
    async def _generic_handler(request: Request, exc: LibraryMindError) -> JSONResponse:
        log.error("library_mind.error", detail=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

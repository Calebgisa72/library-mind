"""FastAPI application factory.

This is the composition root: it wires settings, logging, middleware, and
routers into a single ASGI app. No business logic lives here — routers
delegate to services, and services delegate to providers/infrastructure.

The factory pattern (``create_app``) keeps the app instance construction
testable and avoids import-time side effects.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.core.logging import configure_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Construction order is deliberate:

    1. Load settings (fails fast if required env vars are missing).
    2. Configure structured logging before anything else logs.
    3. Build the bare FastAPI instance with metadata.
    4. Register middleware (CORS, request-id, error handlers) — added in
       later phases.
    5. Mount routers — added in later phases.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="AI-powered intelligent library assistant.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # TODO(phase-2): register middleware (CORS, request-id, global exception handler).
    # TODO(phase-7): mount routers from app.api.{search,chat,classify,summarise,health}.

    return app


# Lazy module-level instance so `uvicorn app.main:app` works.
app = create_app()

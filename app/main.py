"""FastAPI application factory.

This is the composition root: it wires settings, logging, middleware,
exception handlers, and routers into a single ASGI app.  No business logic
lives here — routers delegate to services, and services delegate to
providers/infrastructure.

The factory pattern (``create_app``) keeps the app instance construction
testable and avoids import-time side effects.

Construction order is deliberate:

1. Load settings (fails fast if required env vars are missing).
2. Configure structured logging before anything else logs.
3. Build the bare FastAPI instance with metadata.
4. Add middleware (CORS must come before request-ID so the request-ID is
   visible in CORS-preflight response headers).
5. Register global exception handlers (narrower exceptions first so FastAPI
   matches the most specific type).
6. Mount domain routers.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app import __version__
from app.api.middleware import RequestIDMiddleware, register_exception_handlers
from app.api.routers import chat, classify, health, search, summarise
from app.core.logging import configure_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="AI-powered intelligent library assistant.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        # orjson is already in deps; using it as the default response class
        # gives faster serialisation for all endpoints at no extra cost.
        default_response_class=ORJSONResponse,
    )

    # ── Middleware (registration order = outermost-first at request time) ──
    # CORS must wrap everything so preflight OPTIONS requests are handled
    # before the request-ID middleware or any route handler runs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # ── Global exception handlers (narrower handlers registered first) ─────
    register_exception_handlers(app)

    # ── Domain routers ─────────────────────────────────────────────────────
    app.include_router(search.router)
    app.include_router(chat.router)
    app.include_router(classify.router)
    app.include_router(summarise.router)
    app.include_router(health.router)

    return app


# Lazy module-level instance so `uvicorn app.main:app` works.
app = create_app()

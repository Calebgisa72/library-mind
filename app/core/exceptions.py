"""Domain exception hierarchy.

A small, intention-revealing exception tree makes the global error
handler (registered in Phase 7) able to map domain failures to the
correct HTTP status code without scattering ``HTTPException`` raises
across the service layer.

Hierarchy::

    LibraryMindError                  (base, never raised directly)
    ├── ConfigurationError            (startup-time misconfiguration)
    ├── ProviderError                 (anything the AI layer raises)
    │   ├── ProviderUnavailableError  → 503
    │   └── AllProvidersFailedError   → 503
    ├── RateLimitExceededError        → 429
    ├── ValidationError               → 422  (input that Pydantic missed)
    ├── NotFoundError                 → 404
    └── CacheError                    (logged, never bubbled to clients)

Concrete handlers are wired in :mod:`app.api` later.
"""

from __future__ import annotations

from typing import Any


class LibraryMindError(Exception):
    """Root of the LibraryMind exception tree.

    Carries an optional ``detail`` payload for structured error responses.
    """

    default_message: str = "An internal error occurred."

    def __init__(self, message: str | None = None, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.default_message)
        self.detail: dict[str, Any] = detail or {}


# ── Configuration ────────────────────────────────────────────────────────────
class ConfigurationError(LibraryMindError):
    """Raised at startup when settings cannot be loaded or are invalid."""

    default_message = "Application is misconfigured."


# ── Providers ────────────────────────────────────────────────────────────────
class ProviderError(LibraryMindError):
    """Base class for AI-provider failures."""

    default_message = "AI provider request failed."


class ProviderUnavailableError(ProviderError):
    """A single provider is temporarily unreachable or rate-limited."""

    default_message = "AI provider is temporarily unavailable."


class AllProvidersFailedError(ProviderError, RuntimeError):
    """The resilient orchestrator exhausted every configured provider.

    Multiply-inherits from ``RuntimeError`` so it satisfies the literal
    wording of the lab brief Part 1 acceptance criterion: *"If all
    providers are down, a RuntimeError is raised with a helpful message."*
    Tests that check ``isinstance(exc, RuntimeError)`` succeed; the
    exception is still a fully-fledged member of our ``LibraryMindError``
    tree, so the global handler maps it to HTTP 503 cleanly.
    """

    default_message = "All AI providers failed. Please try again later."


# ── Rate limiting ────────────────────────────────────────────────────────────
class RateLimitExceededError(LibraryMindError):
    """The token-bucket limiter rejected the request."""

    default_message = "Rate limit exceeded. Slow down."


# ── Input validation (beyond what Pydantic catches) ──────────────────────────
class ValidationError(LibraryMindError):
    """Domain-level validation failure (Pydantic schema passed but invariants
    expressed in code do not hold)."""

    default_message = "Invalid input."


# ── Resource lookup ──────────────────────────────────────────────────────────
class NotFoundError(LibraryMindError):
    """A requested resource (conversation, book, etc.) does not exist."""

    default_message = "Resource not found."


# ── Cache ────────────────────────────────────────────────────────────────────
class CacheError(LibraryMindError):
    """Cache operation failed. Should be logged and swallowed — caching is
    a best-effort optimisation, never a correctness guarantee."""

    default_message = "Cache operation failed."

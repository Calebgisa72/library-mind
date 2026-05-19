"""Error response schema used for OpenAPI documentation.

Every non-422 error returns ``{"detail": "Human-readable explanation."}``
which matches FastAPI's default ``HTTPException`` shape.  This model makes
the contract explicit in the generated OpenAPI schema so Swagger UI shows
the correct response body for 429, 503, and 500 responses.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Generic error envelope used for 4xx / 5xx responses."""

    model_config = ConfigDict(extra="forbid")

    detail: str


__all__ = ["ErrorResponse"]

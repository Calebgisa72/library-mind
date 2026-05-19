"""Pydantic request/response schemas for POST /chat.

Length constraints mirror ``docs/API_REFERENCE.md``:

* ``conversation_id`` -- 1..64 characters
* ``message``         -- 1..4000 characters

The response echoes the ``conversation_id`` back so the caller can
correlate multi-turn replies without maintaining server-side state.
Sources share the same shape as the RAG ask endpoint (title, author,
score) and are imported from ``app.schemas.search`` to avoid drift.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.search import SourceBook


class ChatRequest(BaseModel):
    """Request payload for ``POST /chat``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Caller-supplied conversation identifier (UUIDs recommended).",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Patron's latest message.",
    )


class ChatResponse(BaseModel):
    """Response payload for ``POST /chat``."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    reply: str
    sources: list[SourceBook]


__all__ = ["ChatRequest", "ChatResponse"]

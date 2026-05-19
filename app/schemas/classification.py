"""Pydantic request schema for POST /classify/ticket.

The response reuses :class:`~app.services.classifier.TicketClassification`
directly — it is a Pydantic ``BaseModel`` and FastAPI serialises it without
extra wiring.

Length constraints mirror ``docs/API_REFERENCE.md``:

* ``text`` -- 5..4000 characters
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClassifyTicketRequest(BaseModel):
    """Request payload for ``POST /classify/ticket``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Raw support-ticket text to classify.",
    )


__all__ = ["ClassifyTicketRequest"]

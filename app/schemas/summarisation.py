"""Pydantic request schema for POST /summarise/reviews.

The response reuses :class:`~app.services.summariser.ReviewSummary`
directly — it is a Pydantic ``BaseModel`` and FastAPI serialises it without
extra wiring.

Length constraints mirror ``docs/API_REFERENCE.md``:

* ``reviews``       -- list of 1..50 items
* each ``reviews[i]`` -- 5..4000 characters
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Individual review string: 5-4000 characters each.
ReviewText = Annotated[str, Field(min_length=5, max_length=4000)]


class SummariseReviewsRequest(BaseModel):
    """Request payload for ``POST /summarise/reviews``."""

    model_config = ConfigDict(extra="forbid")

    reviews: list[ReviewText] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of 1-50 review strings (each 5-4000 characters).",
    )


__all__ = ["SummariseReviewsRequest"]

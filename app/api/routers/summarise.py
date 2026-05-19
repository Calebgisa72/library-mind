"""Router for book-review summarisation.

Endpoint
--------
POST /summarise/reviews
    Aggregate 1-50 reviews into a structured analysis covering overall
    sentiment, estimated rating, themes, praise, criticism, and a
    one-sentence recommendation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_summariser_service
from app.schemas.errors import ErrorResponse
from app.schemas.summarisation import SummariseReviewsRequest
from app.services.summariser import ReviewSummary, SummariserService

router = APIRouter(tags=["Summarise"])


@router.post(
    "/summarise/reviews",
    response_model=ReviewSummary,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {
            "model": ErrorResponse,
            "description": "AI provider unavailable or returned invalid JSON",
        },
    },
    summary="Summarise book reviews",
    description=(
        "Aggregate 1-50 reader reviews into a structured summary with sentiment, "
        "themes, praise, criticism, estimated rating, and a recommendation."
    ),
)
async def summarise_reviews(
    body: SummariseReviewsRequest,
    summariser: SummariserService = Depends(get_summariser_service),
) -> ReviewSummary:
    """Summarise the provided reviews and return structured analysis."""
    return await summariser.summarise(body.reviews)

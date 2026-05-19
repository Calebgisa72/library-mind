"""Router for support-ticket classification.

Endpoint
--------
POST /classify/ticket
    Classify a free-text support ticket into category, priority, sentiment,
    department, and a one-sentence summary.  Uses low-temperature generation
    for deterministic, consistent outputs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_classifier_service
from app.schemas.classification import ClassifyTicketRequest
from app.schemas.errors import ErrorResponse
from app.services.classifier import ClassifierService, TicketClassification

router = APIRouter(tags=["Classify"])


@router.post(
    "/classify/ticket",
    response_model=TicketClassification,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {
            "model": ErrorResponse,
            "description": "AI provider unavailable or returned invalid JSON",
        },
    },
    summary="Classify a support ticket",
    description=(
        "Classify a raw library support ticket into structured fields: "
        "category, priority, sentiment, suggested department, and summary."
    ),
)
async def classify_ticket(
    body: ClassifyTicketRequest,
    classifier: ClassifierService = Depends(get_classifier_service),
) -> TicketClassification:
    """Classify the ticket and return the structured result."""
    return await classifier.classify(body.text)

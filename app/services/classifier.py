"""Ticket classification service.

:class:`ClassifierService` accepts a raw support-ticket string and returns a
:class:`TicketClassification` Pydantic model containing the ticket's
category, priority, sentiment, suggested routing department, and a
one-sentence summary.

Pipeline::

    ResilientAIService.generate(ticket_text, system=CLASSIFIER_SYSTEM_PROMPT,
                                temperature=0.1, max_tokens=300)
        -> parse_ai_json(raw_response)       -- strips ``` fences
        -> TicketClassification(**payload)   -- Pydantic enum validation
        -> return

Design decisions
----------------
* **No rate-limiter.**  The rate limiter is applied at the API layer
  uniformly across all endpoints.  Pulling it into the service would
  duplicate the concern and make the constructor overly complex.

* **No usage tracker.**  Same reasoning as the rate limiter.  Usage tracking
  for generation calls is wired at the API layer.

* **Pydantic model, not dataclass.**  ``TicketClassification`` is a Pydantic
  ``BaseModel`` rather than a frozen dataclass.  This lets the Phase 7 router
  return it directly as the response body (FastAPI serialises ``BaseModel``
  natively) and gives us Pydantic's enum-coercion and field-constraint
  validation for free.  The enum values are ``Literal`` types so mypy catches
  any drift between the prompt and the response contract.

* **ProviderError on parse/validation failure.**  Both ``parse_ai_json`` and
  the Pydantic ``model_validate`` call raise ``ProviderError`` on failure so
  the global exception handler maps them to HTTP 503.  The raw response is
  preserved in ``detail`` to aid debugging.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.prompts.classifier import (
    CLASSIFIER_MAX_TOKENS,
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFIER_TEMPERATURE,
)
from app.providers.resilient import ResilientAIService
from app.services.json_utils import parse_ai_json

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class TicketClassification(BaseModel):
    """Structured classification of a library support ticket.

    All enum fields are ``Literal`` types so Pydantic raises a
    ``ValidationError`` — surfaced as ``ProviderError`` — when the model
    returns an unexpected value, rather than silently storing it.
    """

    category: Literal["account", "borrowing", "technical", "complaint", "suggestion", "general"]
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "neutral", "negative"]
    department: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=240)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ClassifierService:
    """Classifies a raw support-ticket string into structured fields.

    Parameters
    ----------
    ai_service:
        Resilient multi-provider AI orchestrator.  Called once per
        classification with low temperature for deterministic output.
    """

    def __init__(self, *, ai_service: ResilientAIService) -> None:
        self._ai = ai_service

    async def classify(self, text: str) -> TicketClassification:
        """Classify *text* and return a structured :class:`TicketClassification`.

        Parameters
        ----------
        text:
            Raw support-ticket string.

        Returns
        -------
        TicketClassification
            Parsed and validated classification.

        Raises
        ------
        ProviderError
            When the AI returns non-JSON output or a value outside the
            expected enums.  The exception carries the raw response in
            ``detail`` for diagnostics.
        AllProvidersFailedError
            When every configured AI provider fails to generate.
        """
        log.info("classifier.classify", text_length=len(text))

        result = await self._ai.generate(
            text,
            system=CLASSIFIER_SYSTEM_PROMPT,
            temperature=CLASSIFIER_TEMPERATURE,
            max_tokens=CLASSIFIER_MAX_TOKENS,
        )

        payload = parse_ai_json(result.text)

        try:
            classification = TicketClassification.model_validate(payload)
        except Exception as exc:
            raise ProviderError(
                "AI model returned a classification with invalid field values",
                detail={"raw_response": result.text, "parse_error": str(exc)},
            ) from exc

        log.info(
            "classifier.result",
            category=classification.category,
            priority=classification.priority,
            sentiment=classification.sentiment,
        )
        return classification


__all__ = ["ClassifierService", "TicketClassification"]

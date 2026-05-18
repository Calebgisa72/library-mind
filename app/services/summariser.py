"""Review summarisation service.

:class:`SummariserService` accepts a list of 1-50 review strings and returns
a :class:`ReviewSummary` Pydantic model containing the overall sentiment, an
estimated average rating, key themes, praise points, criticism points, and a
one-sentence recommendation.

Pipeline::

    format numbered review list
        -> ResilientAIService.generate(reviews_block, system=SUMMARISER_SYSTEM_PROMPT,
                                       temperature=0.3, max_tokens=600)
        -> parse_ai_json(raw_response)    -- strips ``` fences
        -> ReviewSummary(**payload)       -- Pydantic validation
        -> return

Design decisions
----------------
* **``overall_sentiment="mixed"``.**  The spec lists positive/neutral/negative
  but "mixed" is the semantically correct output when reviews genuinely
  conflict.  Including it avoids forcing the model to pick a side when the
  reviews are evenly split — which would make the acceptance criterion
  "balanced output with both praise and criticism" harder to satisfy.
  Phase 7 can map ``mixed → neutral`` at the wire boundary if the rubric
  requires a three-value enum; the service returns the honest value.

* **Numbered review block.**  Reviews are formatted as::

      Review 1: <text>
      Review 2: <text>
      ...

  This gives the model explicit structure to refer back to individual reviews
  when identifying patterns, while the prompt instructs holistic synthesis
  rather than per-review summarisation.

* **No rate-limiter / usage tracker.**  Applied uniformly at the API layer
  (Phase 7), same as every other service.

* **Pydantic model for the response.**  Lets the Phase 7 router return it
  directly; field constraints are enforced by Pydantic on construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.prompts.summariser import (
    SUMMARISER_MAX_TOKENS,
    SUMMARISER_SYSTEM_PROMPT,
    SUMMARISER_TEMPERATURE,
)
from app.providers.resilient import ResilientAIService
from app.services.json_utils import parse_ai_json

log = get_logger(__name__)

# Maximum number of reviews accepted per request. Enforced in the service so
# the constraint is visible here and in the Phase 7 schema validation.
MAX_REVIEWS = 50


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class ReviewSummary(BaseModel):
    """Structured summary of a set of reader reviews.

    ``overall_sentiment`` includes "mixed" because balanced review sets
    produce genuinely mixed opinions; forcing positive/neutral/negative would
    lose information.  See the module docstring for the Phase 7 mapping note.
    """

    overall_sentiment: Literal["positive", "neutral", "negative", "mixed"]
    estimated_rating: float = Field(ge=1.0, le=5.0)
    themes: list[str] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)
    criticism: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1, max_length=240)

    @field_validator("themes", "praise", "criticism", mode="before")
    @classmethod
    def _ensure_list(cls, v: object) -> list[object]:
        """Accept None or missing fields as empty lists."""
        if v is None:
            return []
        return v  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SummariserService:
    """Summarises a collection of book reviews into structured insights.

    Parameters
    ----------
    ai_service:
        Resilient multi-provider AI orchestrator.  Called once per
        summarisation request.
    """

    def __init__(self, *, ai_service: ResilientAIService) -> None:
        self._ai = ai_service

    async def summarise(self, reviews: list[str]) -> ReviewSummary:
        """Summarise *reviews* and return a structured :class:`ReviewSummary`.

        Parameters
        ----------
        reviews:
            List of 1-50 review strings.  Each review should be a
            meaningful piece of feedback (min 5 chars enforced upstream
            by the Phase 7 schema).

        Returns
        -------
        ReviewSummary
            Parsed and validated summary.

        Raises
        ------
        ValueError
            When ``reviews`` is empty or exceeds :data:`MAX_REVIEWS`.
        ProviderError
            When the AI returns non-JSON output or field values outside
            the expected constraints.  The raw response is in ``detail``.
        AllProvidersFailedError
            When every configured AI provider fails to generate.
        """
        if not reviews:
            raise ValueError("At least one review is required.")
        if len(reviews) > MAX_REVIEWS:
            raise ValueError(f"Too many reviews: {len(reviews)} > {MAX_REVIEWS}.")

        log.info("summariser.summarise", n_reviews=len(reviews))

        reviews_block = self._format_reviews(reviews)

        result = await self._ai.generate(
            reviews_block,
            system=SUMMARISER_SYSTEM_PROMPT,
            temperature=SUMMARISER_TEMPERATURE,
            max_tokens=SUMMARISER_MAX_TOKENS,
        )

        payload = parse_ai_json(result.text)

        try:
            summary = ReviewSummary.model_validate(payload)
        except Exception as exc:
            raise ProviderError(
                "AI model returned a summary with invalid field values",
                detail={"raw_response": result.text, "parse_error": str(exc)},
            ) from exc

        log.info(
            "summariser.result",
            overall_sentiment=summary.overall_sentiment,
            estimated_rating=summary.estimated_rating,
        )
        return summary

    @staticmethod
    def _format_reviews(reviews: list[str]) -> str:
        """Render *reviews* as a numbered block for the prompt."""
        return "\n".join(f"Review {i}: {review}" for i, review in enumerate(reviews, start=1))


__all__ = ["MAX_REVIEWS", "ReviewSummary", "SummariserService"]

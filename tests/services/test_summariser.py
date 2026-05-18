"""Tests for app.services.summariser.SummariserService.

Covers every Phase 6 Part B acceptance criterion:

* 3-5 mixed reviews produce balanced output with both praise and criticism.
* More than 50 reviews raises a validation error.
* All outputs are valid parseable JSON (ensured by the Pydantic model).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ProviderError
from app.services.summariser import MAX_REVIEWS, ReviewSummary, SummariserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BALANCED_SUMMARY = {
    "overall_sentiment": "mixed",
    "estimated_rating": 3.5,
    "themes": ["pacing", "ending", "characters"],
    "praise": ["compelling ending", "vivid characters"],
    "criticism": ["slow pacing in the middle", "weak opening"],
    "recommendation": "Worth recommending to readers patient with a slow build.",
}

_POSITIVE_SUMMARY = {
    "overall_sentiment": "positive",
    "estimated_rating": 4.8,
    "themes": ["adventure", "world-building"],
    "praise": ["imaginative world", "gripping plot"],
    "criticism": [],
    "recommendation": "Highly recommended for fans of epic fantasy.",
}


def _make_generation_result(text: str) -> MagicMock:
    result = MagicMock()
    result.text = text
    result.provider = "openai"
    result.model = "gpt-4o-mini"
    result.prompt_tokens = 200
    result.completion_tokens = 150
    return result


def _make_ai_service(response_text: str) -> MagicMock:
    svc = MagicMock()
    svc.generate = AsyncMock(return_value=_make_generation_result(response_text))
    return svc


def _make_service(response_text: str) -> SummariserService:
    return SummariserService(ai_service=_make_ai_service(response_text))


_MIXED_REVIEWS = [
    "I couldn't put it down.",
    "Tried to like it, gave up after 80 pages.",
    "Pacing dragged in the middle but the ending was excellent.",
    "The characters felt real and I cared about them.",
    "Not my cup of tea but I can see why others love it.",
]


# ---------------------------------------------------------------------------
# Acceptance criteria tests
# ---------------------------------------------------------------------------


class TestMixedReviews:
    """Lab acceptance criterion: "Summarising 3-5 mixed reviews produces balanced
    output with both praise and criticism"."""

    @pytest.mark.anyio
    async def test_three_to_five_mixed_reviews_returns_balanced_summary(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))

        result = await service.summarise(_MIXED_REVIEWS[:3])

        assert isinstance(result, ReviewSummary)
        assert len(result.praise) >= 1, "Expected at least one praise item"
        assert len(result.criticism) >= 1, "Expected at least one criticism item"

    @pytest.mark.anyio
    async def test_five_mixed_reviews_returns_balanced_summary(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))

        result = await service.summarise(_MIXED_REVIEWS)

        assert len(result.praise) >= 1
        assert len(result.criticism) >= 1

    @pytest.mark.anyio
    async def test_mixed_sentiment_returned_for_conflicting_reviews(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))

        result = await service.summarise(_MIXED_REVIEWS)

        assert result.overall_sentiment == "mixed"

    @pytest.mark.anyio
    async def test_estimated_rating_within_valid_range(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))

        result = await service.summarise(_MIXED_REVIEWS)

        assert 1.0 <= result.estimated_rating <= 5.0


class TestValidationBoundaries:
    """Review list size boundaries."""

    @pytest.mark.anyio
    async def test_single_review_accepted(self) -> None:
        service = _make_service(json.dumps(_POSITIVE_SUMMARY))
        result = await service.summarise(["This book is magnificent."])
        assert isinstance(result, ReviewSummary)

    @pytest.mark.anyio
    async def test_fifty_reviews_accepted(self) -> None:
        service = _make_service(json.dumps(_POSITIVE_SUMMARY))
        reviews = ["Great read."] * MAX_REVIEWS
        result = await service.summarise(reviews)
        assert isinstance(result, ReviewSummary)

    @pytest.mark.anyio
    async def test_too_many_reviews_raises_value_error(self) -> None:
        """51 reviews exceed the MAX_REVIEWS cap and must raise ValueError."""
        service = _make_service(json.dumps(_POSITIVE_SUMMARY))
        reviews = ["text"] * (MAX_REVIEWS + 1)

        with pytest.raises(ValueError, match="Too many"):
            await service.summarise(reviews)

    @pytest.mark.anyio
    async def test_empty_reviews_raises_value_error(self) -> None:
        service = _make_service(json.dumps(_POSITIVE_SUMMARY))

        with pytest.raises(ValueError, match="At least one"):
            await service.summarise([])


# ---------------------------------------------------------------------------
# JSON / output validity
# ---------------------------------------------------------------------------


class TestOutputValidity:
    """Lab acceptance criterion: "All outputs are valid JSON that can be parsed
    by json.loads() without errors"."""

    @pytest.mark.anyio
    async def test_result_is_review_summary_instance(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))
        result = await service.summarise(_MIXED_REVIEWS)
        assert isinstance(result, ReviewSummary)

    @pytest.mark.anyio
    async def test_result_serialises_to_valid_json(self) -> None:
        service = _make_service(json.dumps(_BALANCED_SUMMARY))
        result = await service.summarise(_MIXED_REVIEWS)
        # model_dump_json is Pydantic v2's method — produces valid JSON
        raw_json = result.model_dump_json()
        parsed = json.loads(raw_json)
        assert parsed["overall_sentiment"] == result.overall_sentiment

    @pytest.mark.anyio
    async def test_invalid_json_from_provider_raises_provider_error(self) -> None:
        service = _make_service("this is not JSON")

        with pytest.raises(ProviderError):
            await service.summarise(_MIXED_REVIEWS)

    @pytest.mark.anyio
    async def test_fenced_json_is_stripped_and_parsed(self) -> None:
        fenced = f"```json\n{json.dumps(_BALANCED_SUMMARY)}\n```"
        service = _make_service(fenced)

        result = await service.summarise(_MIXED_REVIEWS)

        assert result.overall_sentiment == "mixed"

    @pytest.mark.anyio
    async def test_valid_json_with_invalid_rating_raises_provider_error(self) -> None:
        bad = {**_BALANCED_SUMMARY, "estimated_rating": 9.9}
        service = _make_service(json.dumps(bad))

        with pytest.raises(ProviderError):
            await service.summarise(_MIXED_REVIEWS)


# ---------------------------------------------------------------------------
# Service behaviour
# ---------------------------------------------------------------------------


class TestServiceBehaviour:
    @pytest.mark.anyio
    async def test_all_valid_sentiments_accepted(self) -> None:
        for sentiment in ("positive", "neutral", "negative", "mixed"):
            payload = {**_BALANCED_SUMMARY, "overall_sentiment": sentiment}
            service = _make_service(json.dumps(payload))
            result = await service.summarise(_MIXED_REVIEWS[:1])
            assert result.overall_sentiment == sentiment

    @pytest.mark.anyio
    async def test_empty_criticism_accepted_for_all_positive_reviews(self) -> None:
        service = _make_service(json.dumps(_POSITIVE_SUMMARY))
        result = await service.summarise(["Amazing!", "Loved it!", "Perfect book."])
        assert result.criticism == []

    @pytest.mark.anyio
    async def test_ai_called_with_summariser_system_prompt(self) -> None:
        from app.prompts.summariser import SUMMARISER_SYSTEM_PROMPT

        ai_service = _make_ai_service(json.dumps(_BALANCED_SUMMARY))
        service = SummariserService(ai_service=ai_service)

        await service.summarise(_MIXED_REVIEWS)

        call_kwargs = ai_service.generate.call_args.kwargs
        assert call_kwargs["system"] == SUMMARISER_SYSTEM_PROMPT

    @pytest.mark.anyio
    async def test_reviews_formatted_as_numbered_block(self) -> None:
        """Each review must be prepended with 'Review N:' in the prompt."""
        ai_service = _make_ai_service(json.dumps(_BALANCED_SUMMARY))
        service = SummariserService(ai_service=ai_service)

        reviews = ["First review.", "Second review."]
        await service.summarise(reviews)

        prompt_arg = ai_service.generate.call_args.args[0]
        assert "Review 1: First review." in prompt_arg
        assert "Review 2: Second review." in prompt_arg

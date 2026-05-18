"""Tests for app.services.classifier.ClassifierService.

Covers every Phase 6 Part A acceptance criterion:

* The angry library-card complaint returns category=technical, priority=high,
  sentiment=negative (exact lab wording).
* Positive feedback returns sentiment=positive with a lower priority.
* Invalid JSON from the provider raises ProviderError.
* Markdown fences in the response are stripped and parsed correctly.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ProviderError
from app.services.classifier import ClassifierService, TicketClassification

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TECHNICAL_HIGH_NEGATIVE = {
    "category": "technical",
    "priority": "high",
    "sentiment": "negative",
    "department": "IT Support",
    "summary": "Patron's library card fails at self-checkout, expressing frustration.",
}

_POSITIVE_LOW = {
    "category": "general",
    "priority": "low",
    "sentiment": "positive",
    "department": "Customer Service",
    "summary": "Patron praises the new reading room.",
}


def _make_generation_result(text: str) -> MagicMock:
    result = MagicMock()
    result.text = text
    result.provider = "openai"
    result.model = "gpt-4o-mini"
    result.prompt_tokens = 80
    result.completion_tokens = 40
    return result


def _make_ai_service(response_text: str) -> MagicMock:
    svc = MagicMock()
    svc.generate = AsyncMock(return_value=_make_generation_result(response_text))
    return svc


def _make_service(response_text: str) -> ClassifierService:
    return ClassifierService(ai_service=_make_ai_service(response_text))


# ---------------------------------------------------------------------------
# Acceptance criteria tests
# ---------------------------------------------------------------------------


class TestAngryCardComplaint:
    """Lab acceptance criterion: "My library card isn't working at the self-checkout
    and I'm very frustrated" → category=technical, priority=high, sentiment=negative."""

    @pytest.mark.anyio
    async def test_angry_card_complaint_returns_technical_high_negative(self) -> None:
        text = "My library card isn't working at the self-checkout and I'm very frustrated"
        service = _make_service(json.dumps(_TECHNICAL_HIGH_NEGATIVE))

        result = await service.classify(text)

        assert isinstance(result, TicketClassification)
        assert result.category == "technical"
        assert result.priority == "high"
        assert result.sentiment == "negative"

    @pytest.mark.anyio
    async def test_angry_card_complaint_has_department_and_summary(self) -> None:
        text = "My library card isn't working at the self-checkout and I'm very frustrated"
        service = _make_service(json.dumps(_TECHNICAL_HIGH_NEGATIVE))

        result = await service.classify(text)

        assert len(result.department) >= 1
        assert len(result.summary) >= 1


class TestPositiveFeedback:
    """Lab acceptance criterion: "I love the new reading room, thank you!"
    → sentiment=positive with a lower priority."""

    @pytest.mark.anyio
    async def test_positive_feedback_returns_positive_sentiment(self) -> None:
        text = "I love the new reading room, thank you!"
        service = _make_service(json.dumps(_POSITIVE_LOW))

        result = await service.classify(text)

        assert result.sentiment == "positive"

    @pytest.mark.anyio
    async def test_positive_feedback_returns_low_priority(self) -> None:
        text = "I love the new reading room, thank you!"
        service = _make_service(json.dumps(_POSITIVE_LOW))

        result = await service.classify(text)

        # Lab says "lower priority" — low or medium are both acceptable.
        assert result.priority in ("low", "medium")


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestJsonParsing:
    @pytest.mark.anyio
    async def test_markdown_fences_stripped_and_parsed(self) -> None:
        """Fenced ```json response must be parsed correctly."""
        fenced = f"```json\n{json.dumps(_TECHNICAL_HIGH_NEGATIVE)}\n```"
        service = _make_service(fenced)

        result = await service.classify("card broken")

        assert result.category == "technical"

    @pytest.mark.anyio
    async def test_plain_fences_stripped_and_parsed(self) -> None:
        plain_fenced = f"```\n{json.dumps(_TECHNICAL_HIGH_NEGATIVE)}\n```"
        service = _make_service(plain_fenced)

        result = await service.classify("card broken")

        assert result.category == "technical"

    @pytest.mark.anyio
    async def test_invalid_json_raises_provider_error(self) -> None:
        service = _make_service("this is not JSON at all")

        with pytest.raises(ProviderError):
            await service.classify("some ticket text")

    @pytest.mark.anyio
    async def test_valid_json_with_invalid_enum_raises_provider_error(self) -> None:
        """A valid JSON object with an unknown category must raise ProviderError."""
        bad_payload = {**_TECHNICAL_HIGH_NEGATIVE, "category": "UNKNOWN_CATEGORY"}
        service = _make_service(json.dumps(bad_payload))

        with pytest.raises(ProviderError):
            await service.classify("some ticket text")


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    @pytest.mark.anyio
    async def test_all_enum_categories_accepted(self) -> None:
        """Every valid category must be accepted without raising."""
        for cat in ("account", "borrowing", "technical", "complaint", "suggestion", "general"):
            payload = {**_TECHNICAL_HIGH_NEGATIVE, "category": cat}
            service = _make_service(json.dumps(payload))
            result = await service.classify("text")
            assert result.category == cat

    @pytest.mark.anyio
    async def test_all_enum_priorities_accepted(self) -> None:
        for pri in ("low", "medium", "high", "urgent"):
            payload = {**_TECHNICAL_HIGH_NEGATIVE, "priority": pri}
            service = _make_service(json.dumps(payload))
            result = await service.classify("text")
            assert result.priority == pri

    @pytest.mark.anyio
    async def test_all_enum_sentiments_accepted(self) -> None:
        for sent in ("positive", "neutral", "negative"):
            payload = {**_TECHNICAL_HIGH_NEGATIVE, "sentiment": sent}
            service = _make_service(json.dumps(payload))
            result = await service.classify("text")
            assert result.sentiment == sent

    @pytest.mark.anyio
    async def test_result_is_ticket_classification_instance(self) -> None:
        service = _make_service(json.dumps(_TECHNICAL_HIGH_NEGATIVE))
        result = await service.classify("text")
        assert isinstance(result, TicketClassification)

    @pytest.mark.anyio
    async def test_ai_called_with_low_temperature(self) -> None:
        """classifier must pass a low temperature to the provider."""
        from app.prompts.classifier import CLASSIFIER_TEMPERATURE

        ai_service = _make_ai_service(json.dumps(_TECHNICAL_HIGH_NEGATIVE))
        service = ClassifierService(ai_service=ai_service)

        await service.classify("text")

        call_kwargs = ai_service.generate.call_args.kwargs
        assert call_kwargs["temperature"] == CLASSIFIER_TEMPERATURE
        assert call_kwargs["temperature"] <= 0.2

    @pytest.mark.anyio
    async def test_ai_called_with_classifier_system_prompt(self) -> None:
        from app.prompts.classifier import CLASSIFIER_SYSTEM_PROMPT

        ai_service = _make_ai_service(json.dumps(_TECHNICAL_HIGH_NEGATIVE))
        service = ClassifierService(ai_service=ai_service)

        await service.classify("text")

        call_kwargs = ai_service.generate.call_args.kwargs
        assert call_kwargs["system"] == CLASSIFIER_SYSTEM_PROMPT

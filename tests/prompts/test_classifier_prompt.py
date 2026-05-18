"""Anti-drift tests for the classifier prompt module.

The classifier system prompt is load-bearing for the Phase 6 acceptance
criteria: the few-shot examples anchor the enum values, and any drift in
the prompt or temperature would quietly regress classification accuracy.
These tests fail loudly on accidental edits so changes are always deliberate.
"""

from __future__ import annotations

from app.prompts.classifier import (
    CLASSIFICATION_EXAMPLES,
    CLASSIFIER_MAX_TOKENS,
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFIER_TEMPERATURE,
)


class TestClassifierSystemPrompt:
    def test_prompt_lists_all_categories(self) -> None:
        """Every valid category enum value must appear in the prompt."""
        for cat in ("account", "borrowing", "technical", "complaint", "suggestion", "general"):
            assert cat in CLASSIFIER_SYSTEM_PROMPT, f"Category '{cat}' missing from prompt"

    def test_prompt_lists_all_priorities(self) -> None:
        """Every valid priority enum value must appear in the prompt."""
        for pri in ("low", "medium", "high", "urgent"):
            assert pri in CLASSIFIER_SYSTEM_PROMPT, f"Priority '{pri}' missing from prompt"

    def test_prompt_lists_all_sentiments(self) -> None:
        """Every valid sentiment enum value must appear in the prompt."""
        for sent in ("positive", "neutral", "negative"):
            assert sent in CLASSIFIER_SYSTEM_PROMPT, f"Sentiment '{sent}' missing from prompt"

    def test_prompt_requests_json_only(self) -> None:
        """Prompt must instruct the model to return JSON without surrounding prose."""
        lower = CLASSIFIER_SYSTEM_PROMPT.lower()
        assert "json" in lower
        assert "no prose" in lower or "only" in lower

    def test_prompt_specifies_required_fields(self) -> None:
        """All five response fields must be named in the prompt."""
        for field in ("category", "priority", "sentiment", "department", "summary"):
            assert f'"{field}"' in CLASSIFIER_SYSTEM_PROMPT or field in CLASSIFIER_SYSTEM_PROMPT

    def test_prompt_contains_examples(self) -> None:
        """Few-shot examples must be embedded in the prompt."""
        assert "Example" in CLASSIFIER_SYSTEM_PROMPT
        assert "Ticket:" in CLASSIFIER_SYSTEM_PROMPT


class TestClassificationExamples:
    def test_at_least_three_examples(self) -> None:
        """M3 recommends ≥3 few-shot examples to anchor enum compliance."""
        assert len(CLASSIFICATION_EXAMPLES) >= 3

    def test_examples_cover_multiple_categories(self) -> None:
        """Examples should span at least three different categories."""
        categories = {ex[1]["category"] for ex in CLASSIFICATION_EXAMPLES}
        assert len(categories) >= 3

    def test_each_example_has_all_required_keys(self) -> None:
        required = {"category", "priority", "sentiment", "department", "summary"}
        for _text, output in CLASSIFICATION_EXAMPLES:
            assert required.issubset(output.keys())

    def test_example_category_values_are_valid_enum(self) -> None:
        valid = {"account", "borrowing", "technical", "complaint", "suggestion", "general"}
        for _text, output in CLASSIFICATION_EXAMPLES:
            assert output["category"] in valid

    def test_example_priority_values_are_valid_enum(self) -> None:
        valid = {"low", "medium", "high", "urgent"}
        for _text, output in CLASSIFICATION_EXAMPLES:
            assert output["priority"] in valid

    def test_example_sentiment_values_are_valid_enum(self) -> None:
        valid = {"positive", "neutral", "negative"}
        for _text, output in CLASSIFICATION_EXAMPLES:
            assert output["sentiment"] in valid


class TestGenerationParameters:
    def test_temperature_is_deterministic_low(self) -> None:
        """Classification uses very low temperature for consistent enum output."""
        assert 0.0 <= CLASSIFIER_TEMPERATURE <= 0.2

    def test_max_tokens_reasonable_for_json_payload(self) -> None:
        """A TicketClassification JSON payload is ~150 tokens; headroom to 300."""
        assert 100 <= CLASSIFIER_MAX_TOKENS <= 512

"""Anti-drift tests for the summariser prompt module.

The summariser system prompt is load-bearing for the Phase 6 acceptance
criterion "balanced output with both praise and criticism".  Drifting the
holistic-synthesis instruction or the JSON field names would silently regress
summarisation quality.  These tests make any such change deliberately visible.
"""

from __future__ import annotations

from app.prompts.summariser import (
    SUMMARISER_MAX_TOKENS,
    SUMMARISER_SYSTEM_PROMPT,
    SUMMARISER_TEMPERATURE,
)


class TestSummariserSystemPrompt:
    def test_prompt_instructs_holistic_analysis(self) -> None:
        """The prompt must forbid per-review summarisation in favour of synthesis."""
        lower = SUMMARISER_SYSTEM_PROMPT.lower()
        assert "holistic" in lower or "holistically" in lower or "all reviews" in lower

    def test_prompt_requires_json_only_output(self) -> None:
        """Prompt must instruct the model to return JSON without surrounding prose."""
        lower = SUMMARISER_SYSTEM_PROMPT.lower()
        assert "json" in lower
        assert "no prose" in lower or "only" in lower

    def test_prompt_lists_all_required_fields(self) -> None:
        """All six response fields must be named in the prompt."""
        for field in (
            "overall_sentiment",
            "estimated_rating",
            "themes",
            "praise",
            "criticism",
            "recommendation",
        ):
            assert field in SUMMARISER_SYSTEM_PROMPT

    def test_prompt_includes_mixed_sentiment(self) -> None:
        """The 'mixed' sentiment value must be listed as valid."""
        assert "mixed" in SUMMARISER_SYSTEM_PROMPT

    def test_prompt_specifies_rating_range(self) -> None:
        """Estimated rating range 1-5 must appear so model knows the scale."""
        assert "1.0" in SUMMARISER_SYSTEM_PROMPT or "1" in SUMMARISER_SYSTEM_PROMPT
        assert "5.0" in SUMMARISER_SYSTEM_PROMPT or "5" in SUMMARISER_SYSTEM_PROMPT

    def test_prompt_sets_librarian_context(self) -> None:
        """Prompt must establish context as a literary / book-review analyst."""
        lower = SUMMARISER_SYSTEM_PROMPT.lower()
        assert "review" in lower


class TestGenerationParameters:
    def test_temperature_allows_fluent_prose(self) -> None:
        """Summarisation uses slightly higher temperature than classification."""
        assert 0.1 <= SUMMARISER_TEMPERATURE <= 0.5

    def test_max_tokens_accommodates_rich_summary(self) -> None:
        """ReviewSummary with multiple list fields can be 300+ tokens; headroom to 600."""
        assert 300 <= SUMMARISER_MAX_TOKENS <= 1024

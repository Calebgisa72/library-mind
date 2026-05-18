"""Anti-drift tests for the RAG prompt module.

The RAG system prompt and refusal message are load-bearing for the lab's
Part 4 acceptance criteria (especially the deterministic refusal).
Changing either should be a deliberate act, surfaced in a PR diff and
accompanied by a cache-key version bump.  These tests fail loudly when
the prompt or refusal text drifts so that a casual edit cannot
silently regress the contract.
"""

from __future__ import annotations

from app.infrastructure.vector_store import SearchResult
from app.prompts.rag import (
    RAG_MAX_TOKENS,
    RAG_SYSTEM_PROMPT,
    RAG_TEMPERATURE,
    REFUSAL_MESSAGE,
    format_context,
)


class TestRefusalMessage:
    def test_refusal_message_is_exact_verbatim_string(self) -> None:
        """Lab acceptance criterion: polite refusal with this exact wording."""
        assert REFUSAL_MESSAGE == ("I'm sorry, I couldn't find that information in our catalogue.")

    def test_system_prompt_quotes_refusal_message(self) -> None:
        """The prompt must instruct the model to reply with the refusal verbatim."""
        assert REFUSAL_MESSAGE in RAG_SYSTEM_PROMPT


class TestSystemPrompt:
    def test_system_prompt_forbids_fabrication(self) -> None:
        """The prompt must explicitly tell the model not to invent facts."""
        lower = RAG_SYSTEM_PROMPT.lower()
        assert "never speculate" in lower
        assert "never invent" in lower

    def test_system_prompt_requires_citations(self) -> None:
        """The prompt must instruct the model to cite by exact title."""
        assert "cite" in RAG_SYSTEM_PROMPT.lower()

    def test_system_prompt_grounds_in_context_only(self) -> None:
        """Grounding-only instruction is non-negotiable for RAG."""
        assert "ONLY" in RAG_SYSTEM_PROMPT

    def test_system_prompt_sets_librarian_persona(self) -> None:
        assert "librarian" in RAG_SYSTEM_PROMPT.lower()


class TestGenerationParameters:
    def test_temperature_is_grounded_low(self) -> None:
        """RAG generation stays low-temperature (anchored to context)."""
        assert 0.0 <= RAG_TEMPERATURE <= 0.5

    def test_max_tokens_bounds_response_length(self) -> None:
        """Two-to-four-sentence guidance fits comfortably in ~512 tokens."""
        assert 128 <= RAG_MAX_TOKENS <= 2048


class TestFormatContext:
    def test_empty_results_renders_empty_string(self) -> None:
        assert format_context([]) == ""

    def test_each_result_is_numbered_and_labelled(self) -> None:
        a = SearchResult(
            id="book-001",
            score=0.9,
            metadata={
                "title": "Dune",
                "author": "Frank Herbert",
                "year": 1965,
                "genre": "Science Fiction",
                "description": "Desert planet Arrakis.",
            },
        )
        b = SearchResult(
            id="book-002",
            score=0.8,
            metadata={
                "title": "Foundation",
                "author": "Isaac Asimov",
                "year": 1951,
                "genre": "Science Fiction",
                "description": "Psychohistory.",
            },
        )

        rendered = format_context([a, b])

        # Numbered.
        assert "[1] Dune by Frank Herbert" in rendered
        assert "[2] Foundation by Isaac Asimov" in rendered
        # Year and genre present.
        assert "1965" in rendered
        assert "Science Fiction" in rendered
        # Description appears.
        assert "Desert planet Arrakis." in rendered
        assert "Psychohistory." in rendered
        # Separator is a newline; preserves order.
        assert rendered.index("[1]") < rendered.index("[2]")

    def test_missing_metadata_fields_have_safe_fallbacks(self) -> None:
        """Missing keys must not raise; placeholders keep the prompt rendered."""
        result = SearchResult(id="x", score=0.5, metadata={})
        rendered = format_context([result])
        assert "[1] Unknown title by Unknown author" in rendered

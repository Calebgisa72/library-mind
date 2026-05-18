"""Anti-drift tests for app.prompts.chatbot.

These tests are intentionally strict: they lock down the exported constants
so a casual edit to the prompt doesn't silently break the acceptance criteria.
If you deliberately change the prompt, update these tests to match.
"""

from __future__ import annotations

from app.prompts.chatbot import CHATBOT_SYSTEM_PROMPT, CHATBOT_TEMPERATURE


class TestChatbotSystemPrompt:
    def test_prompt_is_string(self) -> None:
        assert isinstance(CHATBOT_SYSTEM_PROMPT, str)

    def test_prompt_not_empty(self) -> None:
        assert len(CHATBOT_SYSTEM_PROMPT.strip()) > 0

    def test_prompt_contains_librarymind_persona(self) -> None:
        """The librarian persona must be present in the system prompt."""
        assert "LibraryMind" in CHATBOT_SYSTEM_PROMPT

    def test_prompt_contains_no_fabrication_rule(self) -> None:
        """The anti-fabrication rule must be present so the model never invents titles."""
        assert "NOT invent" in CHATBOT_SYSTEM_PROMPT or "Do NOT invent" in CHATBOT_SYSTEM_PROMPT

    def test_prompt_contains_catalogue_context_instruction(self) -> None:
        """The prompt must instruct the model to use the catalogue context block."""
        assert "CATALOGUE CONTEXT" in CHATBOT_SYSTEM_PROMPT

    def test_prompt_contains_no_ai_disclaimer_rule(self) -> None:
        """The model should not break the fourth wall."""
        assert "disclaimers" in CHATBOT_SYSTEM_PROMPT.lower() or "AI" in CHATBOT_SYSTEM_PROMPT

    def test_prompt_is_warm_persona(self) -> None:
        """The librarian persona should be warm and knowledgeable."""
        lower = CHATBOT_SYSTEM_PROMPT.lower()
        assert "warm" in lower or "helpful" in lower or "librarian" in lower


class TestChatbotTemperature:
    def test_temperature_is_float(self) -> None:
        assert isinstance(CHATBOT_TEMPERATURE, float)

    def test_temperature_in_conversational_range(self) -> None:
        """Temperature should be in the 0.6-0.8 range recommended by ARCHITECTURE.md."""
        assert 0.6 <= CHATBOT_TEMPERATURE <= 0.8

    def test_temperature_is_exactly_point_seven(self) -> None:
        """Lock down the exact value so a future accidental change is visible."""
        assert CHATBOT_TEMPERATURE == 0.7

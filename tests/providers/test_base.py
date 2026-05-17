"""Tests for app.providers.base — GenerationResult sanity checks."""

from __future__ import annotations

import dataclasses

import pytest

from app.providers.base import GenerationResult


class TestGenerationResult:
    def test_is_frozen_dataclass(self) -> None:
        """GenerationResult must be immutable (slots=True, frozen=True)."""
        result = GenerationResult(
            text="hello",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=5,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.text = "mutated"  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        result = GenerationResult(
            text="hello",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=5,
        )
        assert result.text == "hello"
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5

    def test_optional_token_fields_accept_none(self) -> None:
        """Providers may omit token counts — None must be accepted."""
        result = GenerationResult(
            text="hi",
            provider="amaliai",
            model="some-model",
            prompt_tokens=None,
            completion_tokens=None,
        )
        assert result.prompt_tokens is None
        assert result.completion_tokens is None

    def test_equality_by_value(self) -> None:
        r1 = GenerationResult("a", "openai", "m", 1, 2)
        r2 = GenerationResult("a", "openai", "m", 1, 2)
        assert r1 == r2

    def test_inequality_different_text(self) -> None:
        r1 = GenerationResult("a", "openai", "m", 1, 2)
        r2 = GenerationResult("b", "openai", "m", 1, 2)
        assert r1 != r2

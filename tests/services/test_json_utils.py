"""Tests for app.services.json_utils.parse_ai_json.

The JSON fence-stripping helper is the single most important quality gate
for structured-output features: every classification and summarisation call
passes through it.  These tests cover the common fence variants observed in
production and verify the error path raises ProviderError with diagnostics.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import ProviderError
from app.services.json_utils import parse_ai_json


class TestFenceStripping:
    def test_plain_json_parses_without_change(self) -> None:
        raw = '{"category": "technical", "priority": "high"}'
        result = parse_ai_json(raw)
        assert result == {"category": "technical", "priority": "high"}

    def test_strips_json_fenced_block(self) -> None:
        """The most common production variant: ```json ... ```"""
        raw = '```json\n{"category": "account"}\n```'
        result = parse_ai_json(raw)
        assert result == {"category": "account"}

    def test_strips_plain_fenced_block(self) -> None:
        """Fence without a language tag: ``` ... ```"""
        raw = '```\n{"category": "borrowing"}\n```'
        result = parse_ai_json(raw)
        assert result == {"category": "borrowing"}

    def test_strips_fences_with_leading_trailing_whitespace(self) -> None:
        raw = '  ```json  \n  {"key": "value"}  \n  ```  '
        result = parse_ai_json(raw)
        assert result == {"key": "value"}

    def test_handles_nested_json_object(self) -> None:
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = parse_ai_json(raw)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_parses_classification_shaped_payload(self) -> None:
        raw = (
            "```json\n"
            '{"category": "technical", "priority": "high", "sentiment": "negative",'
            ' "department": "IT Support", "summary": "Card fails at checkout."}\n'
            "```"
        )
        result = parse_ai_json(raw)
        assert result["category"] == "technical"
        assert result["priority"] == "high"
        assert result["sentiment"] == "negative"

    def test_parses_summary_shaped_payload(self) -> None:
        raw = (
            '{"overall_sentiment": "mixed", "estimated_rating": 3.5,'
            ' "themes": ["pacing"], "praise": ["great ending"],'
            ' "criticism": ["slow start"], "recommendation": "Worth reading."}'
        )
        result = parse_ai_json(raw)
        assert result["overall_sentiment"] == "mixed"
        assert result["estimated_rating"] == pytest.approx(3.5)
        assert result["praise"] == ["great ending"]


class TestErrorHandling:
    def test_raises_provider_error_on_invalid_json(self) -> None:
        with pytest.raises(ProviderError) as exc_info:
            parse_ai_json("this is not json at all")
        assert "non-JSON" in str(exc_info.value)

    def test_error_detail_contains_raw_response(self) -> None:
        raw = "not json"
        with pytest.raises(ProviderError) as exc_info:
            parse_ai_json(raw)
        assert exc_info.value.detail["raw_response"] == raw

    def test_error_detail_contains_cleaned_string(self) -> None:
        raw = "not json"
        with pytest.raises(ProviderError) as exc_info:
            parse_ai_json(raw)
        assert "cleaned" in exc_info.value.detail

    def test_error_detail_contains_json_error(self) -> None:
        with pytest.raises(ProviderError) as exc_info:
            parse_ai_json("{broken")
        assert "json_error" in exc_info.value.detail

    def test_raises_provider_error_on_empty_string(self) -> None:
        with pytest.raises(ProviderError):
            parse_ai_json("")

    def test_raises_provider_error_on_fenced_non_json(self) -> None:
        """Even when fences are stripped, bad content raises ProviderError."""
        raw = "```json\nnot valid json\n```"
        with pytest.raises(ProviderError):
            parse_ai_json(raw)

    def test_provider_error_is_raised_from_json_decode_error(self) -> None:
        """Exception chaining must be preserved for traceability."""
        import json

        with pytest.raises(ProviderError) as exc_info:
            parse_ai_json("bad")
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

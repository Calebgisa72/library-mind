"""Tests for app.providers.anthropic_provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

from app.core.exceptions import ProviderUnavailableError
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import GenerationResult


def _make_anthropic_rate_limit_error() -> anthropic.RateLimitError:
    """Construct a minimal anthropic.RateLimitError suitable for unit tests."""
    mock_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    mock_response = httpx.Response(429, request=mock_request)
    return anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=mock_response,
        body=None,
    )


def _make_anthropic_message(text: str = "hello", input_tokens: int = 8, output_tokens: int = 4) -> MagicMock:
    """Return a mock anthropic.Message with the standard shape."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    content_block = MagicMock()
    content_block.text = text

    message = MagicMock()
    message.content = [content_block]
    message.usage = usage
    return message


@pytest.fixture()
def provider() -> AnthropicProvider:
    return AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-haiku-latest")


class TestAnthropicProviderGenerate:
    async def test_generate_returns_generation_result(self, provider: AnthropicProvider) -> None:
        """Happy-path: generate() returns a GenerationResult with text."""
        mock_message = _make_anthropic_message("Bonjour!")

        with patch.object(
            provider._client.messages,
            "create",
            new=AsyncMock(return_value=mock_message),
        ):
            result = await provider.generate("Say hello in French.")

        assert isinstance(result, GenerationResult)
        assert result.text == "Bonjour!"
        assert result.provider == "anthropic"
        assert result.model == "claude-3-5-haiku-latest"
        assert result.prompt_tokens == 8
        assert result.completion_tokens == 4

    async def test_system_prompt_included(self, provider: AnthropicProvider) -> None:
        """System prompt must be forwarded in the 'system' kwarg."""
        mock_message = _make_anthropic_message()
        captured_kwargs: list[dict[str, object]] = []

        async def capture(**kwargs: object) -> MagicMock:
            captured_kwargs.append(dict(kwargs))
            return mock_message

        with patch.object(provider._client.messages, "create", new=capture):
            await provider.generate("hello", system="Be concise.")

        assert captured_kwargs[0].get("system") == "Be concise."

    async def test_no_system_kwarg_when_system_is_none(self, provider: AnthropicProvider) -> None:
        """When system=None, the 'system' key must NOT appear in the API call."""
        mock_message = _make_anthropic_message()
        captured_kwargs: list[dict[str, object]] = []

        async def capture(**kwargs: object) -> MagicMock:
            captured_kwargs.append(dict(kwargs))
            return mock_message

        with patch.object(provider._client.messages, "create", new=capture):
            await provider.generate("hello")

        assert "system" not in captured_kwargs[0]

    async def test_retries_on_rate_limit_then_succeeds(self, provider: AnthropicProvider) -> None:
        """generate() must retry on RateLimitError and succeed on third attempt."""
        mock_success = _make_anthropic_message("success")
        call_count = 0

        async def flaky(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _make_anthropic_rate_limit_error()
            return mock_success

        with (
            patch.object(provider._client.messages, "create", new=flaky),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await provider.generate("hi")

        assert result.text == "success"
        assert call_count == 3

    async def test_raises_provider_unavailable_after_all_retries_fail(
        self, provider: AnthropicProvider
    ) -> None:
        """After exhausting retries, ProviderUnavailableError must be raised."""

        async def always_fail(**kwargs: object) -> MagicMock:
            raise _make_anthropic_rate_limit_error()

        with (
            patch.object(provider._client.messages, "create", new=always_fail),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            with pytest.raises(ProviderUnavailableError):
                await provider.generate("hi")

    async def test_provider_name_and_model(self, provider: AnthropicProvider) -> None:
        assert provider.name == "anthropic"
        assert provider.model == "claude-3-5-haiku-latest"


class TestAnthropicProviderEmbed:
    async def test_embed_raises_provider_unavailable(self, provider: AnthropicProvider) -> None:
        """Anthropic has no embeddings API — embed() must raise immediately."""
        with pytest.raises(ProviderUnavailableError, match="Anthropic does not provide"):
            await provider.embed("some text")

    async def test_embed_does_not_call_anthropic_api(self, provider: AnthropicProvider) -> None:
        """The error must be raised before any API call is made."""
        with patch.object(
            provider._client.messages, "create", new=AsyncMock()
        ) as mock_create:
            with pytest.raises(ProviderUnavailableError):
                await provider.embed("text")
            mock_create.assert_not_called()

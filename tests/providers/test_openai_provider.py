"""Tests for app.providers.openai_provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from app.core.exceptions import ProviderUnavailableError
from app.providers.base import GenerationResult
from app.providers.openai_provider import OpenAIProvider


def _make_openai_rate_limit_error() -> openai.RateLimitError:
    """Construct a minimal openai.RateLimitError suitable for unit tests."""
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    mock_response = httpx.Response(429, request=mock_request)
    return openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None)


def _make_openai_completion(text: str = "hello", prompt_tokens: int = 10, completion_tokens: int = 5) -> MagicMock:
    """Return a mock chat completion response with the standard OpenAI shape."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]
    completion.usage = usage
    return completion


@pytest.fixture()
def provider() -> OpenAIProvider:
    return OpenAIProvider(
        api_key="sk-test",
        chat_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
    )


class TestOpenAIProviderGenerate:
    async def test_generate_returns_generation_result(self, provider: OpenAIProvider) -> None:
        """Happy-path: generate() returns a GenerationResult with text."""
        mock_response = _make_openai_completion("The answer is 42.")

        with patch.object(
            provider._client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await provider.generate("What is 6 × 7?")

        assert isinstance(result, GenerationResult)
        assert result.text == "The answer is 42."
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5

    async def test_system_prompt_included(self, provider: OpenAIProvider) -> None:
        """System parameter must be forwarded to the API as the first message."""
        mock_response = _make_openai_completion()
        captured: list[list[dict[str, str]]] = []

        async def capture_messages(**kwargs: object) -> MagicMock:
            captured.append(kwargs.get("messages", []))  # type: ignore[arg-type]
            return mock_response

        with patch.object(provider._client.chat.completions, "create", new=capture_messages):
            await provider.generate("hello", system="You are helpful.")

        assert captured[0][0] == {"role": "system", "content": "You are helpful."}
        assert captured[0][1] == {"role": "user", "content": "hello"}

    async def test_retries_on_rate_limit_then_succeeds(self, provider: OpenAIProvider) -> None:
        """generate() must retry on RateLimitError and succeed on third attempt."""
        mock_success = _make_openai_completion("success")
        call_count = 0

        async def flaky(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _make_openai_rate_limit_error()
            return mock_success

        # Patch asyncio.sleep so tenacity's backoff doesn't slow the test.
        with (
            patch.object(provider._client.chat.completions, "create", new=flaky),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await provider.generate("hi")

        assert result.text == "success"
        assert call_count == 3

    async def test_raises_provider_unavailable_after_all_retries_fail(
        self, provider: OpenAIProvider
    ) -> None:
        """After exhausting retries, ProviderUnavailableError must be raised."""

        async def always_fail(**kwargs: object) -> MagicMock:
            raise _make_openai_rate_limit_error()

        with (
            patch.object(provider._client.chat.completions, "create", new=always_fail),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            with pytest.raises(ProviderUnavailableError):
                await provider.generate("hi")

    async def test_auth_error_raises_provider_unavailable_immediately(
        self, provider: OpenAIProvider
    ) -> None:
        """An AuthenticationError (not transient) surfaces as ProviderUnavailableError."""
        mock_request = httpx.Request("POST", "https://api.openai.com")
        mock_response = httpx.Response(401, request=mock_request)
        auth_error = openai.AuthenticationError("Bad key", response=mock_response, body=None)

        call_count = 0

        async def bad_auth(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            raise auth_error

        with patch.object(provider._client.chat.completions, "create", new=bad_auth):
            with pytest.raises(ProviderUnavailableError):
                await provider.generate("hi")

        # Auth errors are not retried — must be called exactly once.
        assert call_count == 1

    async def test_provider_name_and_model(self, provider: OpenAIProvider) -> None:
        assert provider.name == "openai"
        assert provider.model == "gpt-4o-mini"


class TestOpenAIProviderEmbed:
    async def test_embed_string_returns_single_vector(self, provider: OpenAIProvider) -> None:
        """embed(str) must return a list with exactly one vector."""
        embedding_item = MagicMock()
        embedding_item.embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [embedding_item]

        with patch.object(
            provider._client.embeddings,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await provider.embed("hello")

        assert result == [[0.1, 0.2, 0.3]]

    async def test_embed_list_returns_multiple_vectors(self, provider: OpenAIProvider) -> None:
        """embed([str, str]) must return one vector per input."""
        item1 = MagicMock()
        item1.embedding = [0.1, 0.2]
        item2 = MagicMock()
        item2.embedding = [0.3, 0.4]
        mock_response = MagicMock()
        mock_response.data = [item1, item2]

        with patch.object(
            provider._client.embeddings,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await provider.embed(["a", "b"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

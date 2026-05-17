"""Tests for app.providers.amaliai_provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import ProviderUnavailableError
from app.providers.amaliai_provider import AmaliAIProvider
from app.providers.base import GenerationResult


def _make_httpx_response(
    status_code: int,
    json_data: dict[str, object] | None = None,
) -> MagicMock:
    """Return a MagicMock that behaves like an httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(spec=httpx.Request),
            response=mock,
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


def _chat_response(text: str = "hello", prompt_tokens: int = 5, completion_tokens: int = 3) -> dict[str, object]:
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def _embedding_response(vectors: list[list[float]]) -> dict[str, object]:
    return {"data": [{"embedding": v} for v in vectors]}


@pytest.fixture()
def provider() -> AmaliAIProvider:
    """AmaliAI provider with a pre-injected mock httpx client."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    return AmaliAIProvider(
        api_key="test-key",
        base_url="https://api.amalitech.org/v1",
        chat_model="amali-chat",
        client=mock_client,
    )


class TestAmaliAIProviderGenerate:
    async def test_generate_returns_generation_result(self, provider: AmaliAIProvider) -> None:
        """Happy-path: 200 response produces a GenerationResult."""
        provider._client.post = AsyncMock(  # type: ignore[method-assign]
            return_value=_make_httpx_response(200, _chat_response("Great book!"))
        )

        result = await provider.generate("Recommend a book.")

        assert isinstance(result, GenerationResult)
        assert result.text == "Great book!"
        assert result.provider == "amaliai"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 3

    async def test_429_treated_as_transient(self, provider: AmaliAIProvider) -> None:
        """HTTP 429 must be retried; succeeds on the third attempt."""
        call_count = 0

        async def flaky_post(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return _make_httpx_response(429)
            return _make_httpx_response(200, _chat_response("ok"))

        provider._client.post = flaky_post  # type: ignore[method-assign]

        with patch("asyncio.sleep", new=AsyncMock()):
            result = await provider.generate("hello")

        assert result.text == "ok"
        assert call_count == 3

    async def test_5xx_treated_as_transient(self, provider: AmaliAIProvider) -> None:
        """HTTP 503 must be retried and succeed on the third attempt."""
        call_count = 0

        async def flaky_post(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return _make_httpx_response(503)
            return _make_httpx_response(200, _chat_response("ok"))

        provider._client.post = flaky_post  # type: ignore[method-assign]

        with patch("asyncio.sleep", new=AsyncMock()):
            result = await provider.generate("hello")

        assert result.text == "ok"
        assert call_count == 3

    async def test_raises_after_all_retries_exhausted(self, provider: AmaliAIProvider) -> None:
        """ProviderUnavailableError after exhausting all retry attempts."""
        provider._client.post = AsyncMock(  # type: ignore[method-assign]
            return_value=_make_httpx_response(429)
        )

        with (
            patch("asyncio.sleep", new=AsyncMock()),
            pytest.raises(ProviderUnavailableError),
        ):
            await provider.generate("hello")

    async def test_network_timeout_treated_as_transient(self, provider: AmaliAIProvider) -> None:
        """httpx.TimeoutException is retried and succeeds on the third attempt."""
        call_count = 0

        async def flaky_post(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timed out")
            return _make_httpx_response(200, _chat_response("recovered"))

        provider._client.post = flaky_post  # type: ignore[method-assign]

        with patch("asyncio.sleep", new=AsyncMock()):
            result = await provider.generate("hello")

        assert result.text == "recovered"

    async def test_raises_when_model_not_configured(self) -> None:
        """AmaliAI raises immediately if chat_model is an empty string."""
        # Inject a mock client to avoid real httpx construction (which picks up
        # sandbox SOCKS proxy env vars and requires the socksio package).
        mock_client = MagicMock(spec=httpx.AsyncClient)
        p = AmaliAIProvider(
            api_key="k",
            base_url="https://api.amalitech.org/v1",
            chat_model="",  # intentionally empty
            client=mock_client,
        )
        with pytest.raises(ProviderUnavailableError, match="AMALIAI_CHAT_MODEL"):
            await p.generate("hello")

    async def test_provider_name_and_model(self, provider: AmaliAIProvider) -> None:
        assert provider.name == "amaliai"
        assert provider.model == "amali-chat"


class TestAmaliAIProviderEmbed:
    async def test_embed_returns_vectors(self, provider: AmaliAIProvider) -> None:
        """Happy-path: embed returns one vector per input string."""
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        provider._client.post = AsyncMock(  # type: ignore[method-assign]
            return_value=_make_httpx_response(200, _embedding_response(vectors))
        )

        result = await provider.embed(["foo", "bar"])
        assert result == vectors

    async def test_embed_string_input(self, provider: AmaliAIProvider) -> None:
        """embed(str) must treat the input as a single-item list."""
        provider._client.post = AsyncMock(  # type: ignore[method-assign]
            return_value=_make_httpx_response(200, _embedding_response([[1.0, 2.0]]))
        )

        result = await provider.embed("single")
        assert result == [[1.0, 2.0]]

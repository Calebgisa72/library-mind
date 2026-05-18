"""OpenAI concrete AI provider.

Uses the official openai async client. Supports chat completions
(via generate and generate_chat) and text embeddings (via embed).

Retry policy
------------
Transient errors - rate limits, timeouts, connection drops - are retried up to
three times with exponential backoff before raising ProviderUnavailableError.
Authentication failures (openai.AuthenticationError) are NOT transient
and propagate immediately; the ResilientAIService will fall through to the
next provider and log the failure.

Token accounting
----------------
OpenAI always populates response.usage on chat completion calls; we extract
prompt_tokens and completion_tokens directly. Embedding calls do not
return completion tokens; completion_tokens is set to 0.
"""

from __future__ import annotations

import openai
from openai import AsyncOpenAI

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import GenerationResult
from app.providers.retry import build_provider_retry

log = get_logger(__name__)

# Errors worth retrying: temporary service problems, not auth failures.
_TRANSIENT = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)

_retry = build_provider_retry(_TRANSIENT)


class OpenAIProvider:
    """AI provider backed by the OpenAI API.

    Parameters
    ----------
    api_key:
        OpenAI API key. Never hard-coded - always loaded from settings.
    chat_model:
        The chat-completion model to use (e.g. "gpt-4o-mini").
    embedding_model:
        The embedding model to use (e.g. "text-embedding-3-small").
    """

    name: str = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        embedding_model: str,
    ) -> None:
        self.model = chat_model
        self._embedding_model = embedding_model
        self._client = AsyncOpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Public protocol surface
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Generate a chat completion via the OpenAI API.

        Retries transient errors (rate limits, timeouts) up to three times
        before raising ProviderUnavailableError.
        """
        try:
            return await self._do_generate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except _TRANSIENT as exc:
            # Retries exhausted - convert to our domain exception so the
            # ResilientAIService can fall through to the next provider.
            raise ProviderUnavailableError(f"OpenAI transient error after retries: {exc}") from exc
        except openai.OpenAIError as exc:
            # Non-transient SDK error (auth, invalid request, etc.).
            raise ProviderUnavailableError(f"OpenAI call failed: {exc}") from exc

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Generate a completion from a full conversation history.

        Passes messages directly to the OpenAI chat completions API, which
        natively supports the system / user / assistant role format.
        Retries transient errors with exponential backoff.
        """
        try:
            return await self._do_generate_chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except _TRANSIENT as exc:
            raise ProviderUnavailableError(f"OpenAI transient error after retries: {exc}") from exc
        except openai.OpenAIError as exc:
            raise ProviderUnavailableError(f"OpenAI chat call failed: {exc}") from exc

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings via the OpenAI embeddings API.

        Retries transient errors up to three times before raising
        ProviderUnavailableError.
        """
        try:
            return await self._do_embed(text)
        except _TRANSIENT as exc:
            raise ProviderUnavailableError(
                f"OpenAI embedding transient error after retries: {exc}"
            ) from exc
        except openai.OpenAIError as exc:
            raise ProviderUnavailableError(f"OpenAI embedding call failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Private retry-decorated helpers
    # ------------------------------------------------------------------

    @_retry
    async def _do_generate(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Inner generate call wrapped by the tenacity retry decorator."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.debug(
            "openai.generate.attempt",
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )

    @_retry
    async def _do_generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Inner chat-history generation call wrapped by the tenacity retry decorator."""
        log.debug(
            "openai.generate_chat.attempt",
            model=self.model,
            n_messages=len(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )

    @_retry
    async def _do_embed(self, text: str | list[str]) -> list[list[float]]:
        """Inner embed call wrapped by the tenacity retry decorator."""
        texts = [text] if isinstance(text, str) else list(text)

        log.debug(
            "openai.embed.attempt",
            model=self._embedding_model,
            n_texts=len(texts),
        )

        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

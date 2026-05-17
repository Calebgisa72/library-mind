"""Anthropic (Claude) concrete AI provider.

Uses the official ``anthropic`` async client.  Anthropic's Messages API
accepts a ``system`` parameter directly, so there is no need to splice the
system message into the ``messages`` list.

Embeddings
----------
Anthropic does not offer an embeddings API.  ``embed()`` raises
``ProviderUnavailableError`` immediately; the ``ResilientAIService`` falls
through to the next provider, and the ``EmbeddingService`` (Phase 3) will try
OpenAI or AmaliAI.

Token accounting
----------------
Anthropic reports ``usage.input_tokens`` and ``usage.output_tokens`` (note the
different field names from OpenAI's ``prompt_tokens`` / ``completion_tokens``).
We normalise to our ``GenerationResult`` fields here so the rest of the app is
insulated from vendor naming differences.
"""

from __future__ import annotations

import anthropic
from anthropic import AsyncAnthropic

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import GenerationResult
from app.providers.retry import build_provider_retry

log = get_logger(__name__)

# Transient errors worth retrying.  ``anthropic.AuthenticationError`` and
# ``anthropic.PermissionDeniedError`` are NOT transient; they propagate
# straight to the outer generate(), which converts them to ProviderUnavailableError.
_TRANSIENT = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)

_retry = build_provider_retry(_TRANSIENT)


class AnthropicProvider:
    """AI provider backed by Anthropic's Claude API.

    Parameters
    ----------
    api_key:
        Anthropic API key.  Loaded from settings; never hard-coded.
    model:
        The Claude model to use (e.g. ``"claude-3-5-haiku-latest"``).
    """

    name: str = "anthropic"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

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
        """Generate a completion via the Anthropic Messages API.

        Retries transient errors (rate limits, timeouts) up to three times
        before raising ``ProviderUnavailableError``.
        """
        try:
            return await self._do_generate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except _TRANSIENT as exc:
            raise ProviderUnavailableError(
                f"Anthropic transient error after retries: {exc}"
            ) from exc
        except anthropic.AnthropicError as exc:
            raise ProviderUnavailableError(f"Anthropic call failed: {exc}") from exc

    async def embed(self, text: str | list[str]) -> list[list[float]]:  # noqa: ARG002
        """Not supported — Anthropic has no embeddings API.

        Raises ``ProviderUnavailableError`` immediately so the resilient service
        or embedding service can fall through to a provider that does offer
        embeddings (OpenAI).
        """
        raise ProviderUnavailableError(
            "Anthropic does not provide an embeddings API. "
            "Configure an OpenAI key for embedding support."
        )

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
        log.debug(
            "anthropic.generate.attempt",
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Anthropic does not accept an empty string for ``system``.
        # Use NOT_GIVEN to omit the field entirely when no system prompt exists.
        kwargs: dict[str, object] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)  # type: ignore[arg-type]

        text = response.content[0].text if response.content else ""
        usage = response.usage
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.input_tokens if usage else None,
            completion_tokens=usage.output_tokens if usage else None,
        )

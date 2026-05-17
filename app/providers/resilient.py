"""Resilient AI service — ordered failover orchestrator.

``ResilientAIService`` maintains an ordered list of ``AIProvider`` instances and
tries them in sequence.  If a provider raises ``ProviderError``, it logs a
warning and falls through to the next.  If every provider fails, it raises
``AllProvidersFailedError`` (a ``RuntimeError`` subclass), satisfying Part 1
acceptance criterion: *"If all providers are down, a RuntimeError is raised
with a helpful message."*

Design notes
------------
* The resilient service itself satisfies the ``AIProvider`` protocol, so a
  caller cannot tell whether it is talking to a single provider or a chain.
* Provider ordering respects ``Settings.configured_providers`` which puts the
  ``PRIMARY_PROVIDER`` first.
* No caching, rate-limiting, or usage tracking here — those wrap this service
  from outside (Phase 2).
* ``from_settings()`` is the canonical factory method so application startup
  code never touches individual provider constructors.
"""

from __future__ import annotations

from app.core.exceptions import AllProvidersFailedError, ProviderError
from app.core.logging import get_logger
from app.core.settings import Settings
from app.providers.base import AIProvider, GenerationResult

log = get_logger(__name__)


class ResilientAIService:
    """Ordered failover orchestrator over a list of ``AIProvider`` instances.

    The service tries each provider in the order supplied at construction.  On
    a ``ProviderError``, it logs the failure and moves on.  Only when every
    provider has been exhausted does it raise ``AllProvidersFailedError``.

    This class satisfies the ``AIProvider`` protocol (it has ``generate`` and
    ``embed`` with matching signatures), so it can be used wherever an
    ``AIProvider`` is expected without revealing that failover is happening.

    Parameters
    ----------
    providers:
        Non-empty ordered list of providers to try.  The first entry is the
        primary provider; subsequent entries are fallbacks.
    """

    def __init__(self, *, providers: list[AIProvider]) -> None:
        if not providers:
            raise ValueError("ResilientAIService requires at least one provider.")
        self._providers = providers
        # Expose ``name`` and ``model`` from the primary provider so this class
        # looks like a regular AIProvider to callers.
        self.name: str = providers[0].name
        self.model: str = providers[0].model

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings) -> ResilientAIService:
        """Build a ``ResilientAIService`` from application settings.

        Providers are instantiated in the order returned by
        ``settings.configured_providers`` (``PRIMARY_PROVIDER`` first).
        Only providers with a key present in settings are included.

        Raises ``ValueError`` if no providers could be built (which should
        not happen in practice because ``Settings._require_at_least_one_provider_key``
        already guards against that at startup).
        """
        # Local imports avoid a circular import through app.providers.__init__.
        from app.providers.amaliai_provider import AmaliAIProvider  # noqa: PLC0415
        from app.providers.anthropic_provider import AnthropicProvider  # noqa: PLC0415
        from app.providers.openai_provider import OpenAIProvider  # noqa: PLC0415

        providers: list[AIProvider] = []

        for provider_name in settings.configured_providers:
            if provider_name == "openai" and settings.openai_api_key:
                providers.append(
                    OpenAIProvider(
                        api_key=settings.openai_api_key,
                        chat_model=settings.openai_chat_model,
                        embedding_model=settings.openai_embedding_model,
                    )
                )
            elif provider_name == "anthropic" and settings.anthropic_api_key:
                providers.append(
                    AnthropicProvider(
                        api_key=settings.anthropic_api_key,
                        model=settings.anthropic_chat_model,
                    )
                )
            elif provider_name == "amaliai" and settings.amaliai_api_key:
                providers.append(
                    AmaliAIProvider(
                        api_key=settings.amaliai_api_key,
                        base_url=settings.amaliai_base_url,
                        chat_model=settings.amaliai_chat_model,
                    )
                )

        if not providers:
            raise ValueError(
                "No AI providers could be constructed from the current settings. "
                "Check that at least one provider key is configured."
            )

        return cls(providers=providers)

    # ------------------------------------------------------------------
    # AIProvider protocol surface
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Attempt generation with each provider in order.

        Returns on the first success.  If all providers raise ``ProviderError``,
        raises ``AllProvidersFailedError`` with a summary of every attempt.

        Part 1 acceptance criteria satisfied:
        - "Calling generate() returns a text response from the primary provider"
        - "Temporarily invalidating the primary provider's API key causes
          automatic fallback to the second provider without crashing"
        - "Retry logic is observable in logs (you can see it retrying before
          falling back)" — satisfied by each provider's tenacity decorator.
        - "If all providers are down, a RuntimeError is raised with a helpful
          message" — AllProvidersFailedError inherits from RuntimeError.
        """
        errors: list[tuple[str, ProviderError]] = []

        for provider in self._providers:
            try:
                log.info("provider.attempt", provider=provider.name, model=provider.model)
                result = await provider.generate(
                    prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                log.info(
                    "provider.success",
                    provider=provider.name,
                    model=provider.model,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                )
                return result
            except ProviderError as exc:
                log.warning(
                    "provider.failed",
                    provider=provider.name,
                    error=str(exc),
                )
                errors.append((provider.name, exc))
                continue

        raise AllProvidersFailedError(
            f"All providers failed: {', '.join(f'{n}={e}' for n, e in errors)}",
            detail={"attempts": [n for n, _ in errors]},
        )

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Attempt embedding with each provider in order.

        Skips providers that raise ``ProviderError`` (including
        ``AnthropicProvider``, which doesn't support embeddings) and falls
        through to the next.  Raises ``AllProvidersFailedError`` if no provider
        succeeds.
        """
        errors: list[tuple[str, ProviderError]] = []

        for provider in self._providers:
            try:
                log.info("provider.embed.attempt", provider=provider.name)
                vectors = await provider.embed(text)
                log.info("provider.embed.success", provider=provider.name)
                return vectors
            except ProviderError as exc:
                log.warning(
                    "provider.embed.failed",
                    provider=provider.name,
                    error=str(exc),
                )
                errors.append((provider.name, exc))
                continue

        raise AllProvidersFailedError(
            f"All providers failed to embed: {', '.join(f'{n}={e}' for n, e in errors)}",
            detail={"attempts": [n for n, _ in errors]},
        )

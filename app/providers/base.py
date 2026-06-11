"""AI provider protocol and shared result types.

All concrete providers (OpenAI, Anthropic, AmaliAI) satisfy the AIProvider
Protocol so the rest of the application talks to one interface, never to a
vendor directly. Adding a fourth provider is a single new file.

Design notes
------------
* Protocol rather than ABC: structural subtyping keeps concrete classes
  testable in isolation - you can pass any object with the right shape without
  inheriting from a base class.
* GenerationResult is a frozen dataclass so callers can trust that no
  intermediate layer mutates the result on its way up the stack.
* prompt_tokens / completion_tokens are int | None because not every provider
  reports usage on every call (some streaming modes omit it).
  Providers that omit usage (the AmaliAI gateway) fill the None case with a
  tiktoken-based count; see app.providers.tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AIProvider(Protocol):
    """Common interface every concrete AI provider must satisfy.

    The generate method is the primary entry-point for text generation.
    generate_chat accepts a full conversation history (Phase 5 chatbot).
    embed exists on the protocol so the EmbeddingService can call
    whichever provider it receives without knowing its concrete type.

    Attributes
    ----------
    name:
        Short identifier used in logs and error messages.
        One of "openai", "anthropic", or "amaliai".
    model:
        The chat/generation model this provider instance is configured to use.
    """

    name: str
    model: str

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Generate a text completion for prompt.

        Parameters
        ----------
        prompt:
            The user-facing input to send to the model.
        system:
            Optional system-level instruction (e.g. persona, format rules).
            Providers that do not support a separate system message prepend it
            to the user content.
        temperature:
            Sampling temperature. Lower values -> more deterministic.
        max_tokens:
            Hard cap on completion length. Set this precisely - models fill
            the budget regardless of need, and every token costs money.

        Returns
        -------
        GenerationResult
            Parsed response with text and token-usage metadata.

        Raises
        ------
        ProviderUnavailableError
            If the provider is temporarily unreachable, rate-limited, or
            returns an error after exhausting retries.
        """
        ...

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Generate a completion from an ordered list of role-tagged messages.

        Unlike generate, which accepts a single prompt string, this method
        accepts the full conversation history so the chatbot can send prior
        turns to the model. The messages list follows the OpenAI chat format:
        each item has "role" ("system", "user", or "assistant") and "content".

        Parameters
        ----------
        messages:
            Full conversation history, including the system message (if any)
            as the first entry and the current user turn as the last.
        temperature:
            Sampling temperature.
        max_tokens:
            Hard cap on completion length.

        Returns
        -------
        GenerationResult
            Parsed response with text and token-usage metadata.

        Raises
        ------
        ProviderUnavailableError
            If the provider is temporarily unreachable or returns an error
            after exhausting retries.
        """
        ...

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Return embedding vector(s) for text.

        Parameters
        ----------
        text:
            A single string or a list of strings to embed in one call.
            Implementations must normalise to a list internally.

        Returns
        -------
        list[list[float]]
            One vector per input string, in input order.

        Raises
        ------
        ProviderUnavailableError
            If the provider does not support embeddings, or if the call fails
            after exhausting retries.
        """
        ...


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Immutable record of a single completed generation call.

    prompt_tokens and completion_tokens are None only when a provider neither
    reports usage nor counts tokens locally. The AmaliAI provider backfills
    missing counts via tiktoken (app.providers.tokens), so cost tracking
    works uniformly across providers.
    """

    text: str
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None

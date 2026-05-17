"""AmaliAI concrete AI provider.

AmaliAI exposes an OpenAI-compatible HTTP API, so we drive it with
``httpx.AsyncClient`` rather than a vendor SDK (no such SDK exists).

Endpoints used
--------------
* ``POST /chat/completions`` — text generation (OpenAI-compatible request/response).
* ``POST /embeddings`` — vector embeddings (OpenAI-compatible).

Retry policy
------------
The inner methods raise ``ProviderUnavailableError`` for 429 and 5xx responses,
making those HTTP statuses retryable via the tenacity decorator (which catches
``ProviderUnavailableError`` as a transient error, alongside network-level
exceptions).  4xx errors that are *not* 429 indicate a permanent client-side
problem (bad request, auth) and propagate immediately.

Error mapping
-------------
* 429 / 5xx → ``ProviderUnavailableError`` (transient, retryable)
* httpx.TimeoutException / httpx.ConnectError → same (transient, retryable)
* Other 4xx → ``ProviderUnavailableError`` (non-transient, propagates)
"""

from __future__ import annotations

import httpx

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import GenerationResult
from app.providers.retry import build_provider_retry

log = get_logger(__name__)

# Transient errors: our own "service unavailable" plus low-level network
# failures.  HTTP 4xx client errors are NOT included — they indicate a
# permanent problem (wrong model name, auth failure) and should not be retried.
_TRANSIENT = (
    ProviderUnavailableError,
    httpx.TimeoutException,
    httpx.ConnectError,
)

_retry = build_provider_retry(_TRANSIENT)

# HTTP status codes that signal a transient server-side problem.
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class AmaliAIProvider:
    """AI provider backed by the AmaliAI OpenAI-compatible HTTP API.

    Parameters
    ----------
    api_key:
        AmaliAI credentials.  Loaded from settings; never hard-coded.
    base_url:
        API root, e.g. ``"https://api.amalitech.org/v1"``.
    chat_model:
        Model identifier for chat completions.  Must be non-empty.
    embedding_model:
        Model identifier for embeddings.  Defaults to the chat model when
        the API exposes a unified model endpoint.
    client:
        Optional pre-constructed ``httpx.AsyncClient``.  Inject in tests to
        avoid real HTTP calls.
    """

    name: str = "amaliai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        chat_model: str,
        embedding_model: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = chat_model
        self._embedding_model = embedding_model or chat_model
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

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
        """Generate a chat completion via the AmaliAI API.

        Raises ``ProviderUnavailableError`` when the chat model is not
        configured (empty string) to fail fast rather than sending a
        malformed request.
        """
        if not self.model:
            raise ProviderUnavailableError(
                "AmaliAI chat model is not configured. " "Set AMALIAI_CHAT_MODEL in your .env file."
            )
        try:
            return await self._do_generate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderUnavailableError(f"AmaliAI network error after retries: {exc}") from exc
        except ProviderUnavailableError:
            raise
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"AmaliAI HTTP error: {exc}") from exc

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings via the AmaliAI embeddings endpoint."""
        try:
            return await self._do_embed(text)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderUnavailableError(
                f"AmaliAI embedding network error after retries: {exc}"
            ) from exc
        except ProviderUnavailableError:
            raise
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"AmaliAI embedding HTTP error: {exc}") from exc

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
        """Inner generate call — raises ProviderUnavailableError on 429/5xx."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log.debug(
            "amaliai.generate.attempt",
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        if response.status_code in _RETRYABLE_STATUSES:
            # Raise our own domain exception so the tenacity decorator retries.
            raise ProviderUnavailableError(f"AmaliAI returned HTTP {response.status_code}")

        response.raise_for_status()
        data = response.json()

        text: str = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    @_retry
    async def _do_embed(self, text: str | list[str]) -> list[list[float]]:
        """Inner embed call — raises ProviderUnavailableError on 429/5xx."""
        texts = [text] if isinstance(text, str) else list(text)

        log.debug(
            "amaliai.embed.attempt",
            model=self._embedding_model,
            n_texts=len(texts),
        )

        response = await self._client.post(
            "/embeddings",
            json={"model": self._embedding_model, "input": texts},
        )

        if response.status_code in _RETRYABLE_STATUSES:
            raise ProviderUnavailableError(
                f"AmaliAI embedding returned HTTP {response.status_code}"
            )

        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

"""Tests for app.providers.resilient — ResilientAIService failover logic.

Covers the four Part 1 acceptance criteria:
1. "Calling generate() returns a text response from the primary provider"
2. "Temporarily invalidating the primary provider's API key causes automatic
   fallback to the second provider without crashing"
3. "Retry logic is observable in logs (you can see it retrying before falling
   back)" — tested via structlog's capture_logs helper.
4. "If all providers are down, a RuntimeError is raised with a helpful message"
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from app.core.exceptions import AllProvidersFailedError, ProviderUnavailableError
from app.providers.base import AIProvider, GenerationResult
from app.providers.resilient import ResilientAIService

# ---------------------------------------------------------------------------
# Helpers / fake providers
# ---------------------------------------------------------------------------


def _make_provider(
    name: str,
    *,
    result: GenerationResult | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock that satisfies the AIProvider protocol."""
    provider = MagicMock(spec=AIProvider)
    provider.name = name
    provider.model = f"{name}-model"

    if raises is not None:
        provider.generate = AsyncMock(side_effect=raises)
        provider.embed = AsyncMock(side_effect=raises)
    else:
        gen_result = result or GenerationResult(
            text=f"hello from {name}",
            provider=name,
            model=f"{name}-model",
            prompt_tokens=5,
            completion_tokens=3,
        )
        provider.generate = AsyncMock(return_value=gen_result)
        provider.embed = AsyncMock(return_value=[[0.1, 0.2]])

    return provider


def _unavailable(name: str = "p") -> MagicMock:
    return _make_provider(name, raises=ProviderUnavailableError(f"{name} unavailable"))


def _ok(name: str = "p") -> MagicMock:
    return _make_provider(name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResilientAIServiceGenerate:
    async def test_primary_succeeds_returns_result(self) -> None:
        """Acceptance criterion 1: primary provider returns successfully."""
        primary = _ok("openai")
        fallback = _ok("anthropic")
        svc = ResilientAIService(providers=[primary, fallback])

        result = await svc.generate("hello")

        assert result.provider == "openai"
        # Fallback must NOT have been called.
        fallback.generate.assert_not_called()

    async def test_primary_fails_fallback_succeeds(self) -> None:
        """Acceptance criterion 2: primary failure causes clean fallback."""
        primary = _unavailable("openai")
        fallback = _ok("anthropic")
        svc = ResilientAIService(providers=[primary, fallback])

        result = await svc.generate("hello")

        assert result.provider == "anthropic"
        primary.generate.assert_awaited_once()
        fallback.generate.assert_awaited_once()

    async def test_all_fail_raises_runtime_error(self) -> None:
        """Acceptance criterion 4: AllProvidersFailedError is a RuntimeError."""
        svc = ResilientAIService(providers=[_unavailable("openai"), _unavailable("anthropic")])

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await svc.generate("hello")

        # The lab criterion requires isinstance(exc, RuntimeError) is True.
        assert isinstance(exc_info.value, RuntimeError)

    async def test_all_fail_error_message_contains_provider_names(self) -> None:
        """The error message must mention which providers were attempted."""
        svc = ResilientAIService(providers=[_unavailable("openai"), _unavailable("anthropic")])

        with pytest.raises(AllProvidersFailedError, match="openai"):
            await svc.generate("hello")

    async def test_logs_provider_failed_on_failure(self) -> None:
        """Acceptance criterion 3: provider.failed warning is emitted when a
        provider fails so that retry/fallback is observable in logs."""
        svc = ResilientAIService(providers=[_unavailable("openai"), _ok("anthropic")])

        with structlog.testing.capture_logs() as log_entries:
            await svc.generate("hello")

        warning_events = [e for e in log_entries if e.get("log_level") == "warning"]
        assert any(
            e.get("event") == "provider.failed" and e.get("provider") == "openai"
            for e in warning_events
        ), f"Expected 'provider.failed' warning not found in: {log_entries}"

    async def test_logs_provider_attempt_on_each_try(self) -> None:
        """An INFO log with event 'provider.attempt' is emitted per attempt."""
        primary = _unavailable("openai")
        fallback = _ok("anthropic")
        svc = ResilientAIService(providers=[primary, fallback])

        with structlog.testing.capture_logs() as log_entries:
            await svc.generate("hello")

        attempt_events = [e for e in log_entries if e.get("event") == "provider.attempt"]
        provider_names = [e["provider"] for e in attempt_events]
        assert "openai" in provider_names
        assert "anthropic" in provider_names

    async def test_three_providers_second_also_fails(self) -> None:
        """Failover skips multiple failed providers and returns from the third."""
        p1 = _unavailable("openai")
        p2 = _unavailable("anthropic")
        p3 = _ok("amaliai")
        svc = ResilientAIService(providers=[p1, p2, p3])

        result = await svc.generate("hello")
        assert result.provider == "amaliai"

    async def test_requires_at_least_one_provider(self) -> None:
        with pytest.raises(ValueError, match="at least one provider"):
            ResilientAIService(providers=[])

    async def test_error_detail_lists_attempted_providers(self) -> None:
        """AllProvidersFailedError.detail must carry the list of attempted names."""
        svc = ResilientAIService(providers=[_unavailable("openai"), _unavailable("anthropic")])

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await svc.generate("hello")

        assert "openai" in exc_info.value.detail["attempts"]
        assert "anthropic" in exc_info.value.detail["attempts"]


class TestResilientAIServiceEmbed:
    async def test_embed_primary_succeeds(self) -> None:
        """Embed returns from the first provider that succeeds."""
        p1 = _ok("openai")
        p2 = _ok("anthropic")
        svc = ResilientAIService(providers=[p1, p2])

        result = await svc.embed("query")
        assert result == [[0.1, 0.2]]
        p2.embed.assert_not_called()

    async def test_embed_falls_through_on_failure(self) -> None:
        """If primary can't embed (e.g. Anthropic), fallback is tried."""
        p1 = _unavailable("anthropic")
        p2 = _ok("openai")
        svc = ResilientAIService(providers=[p1, p2])

        result = await svc.embed("text")
        assert result == [[0.1, 0.2]]

    async def test_embed_all_fail_raises_all_providers_failed(self) -> None:
        svc = ResilientAIService(providers=[_unavailable("openai"), _unavailable("anthropic")])

        with pytest.raises(AllProvidersFailedError):
            await svc.embed("text")


class TestResilientAIServiceAttributes:
    def test_name_and_model_reflect_primary_provider(self) -> None:
        """The service exposes name/model from the first provider."""
        p1 = _ok("openai")
        p1.model = "gpt-4o-mini"
        svc = ResilientAIService(providers=[p1])
        assert svc.name == "openai"
        assert svc.model == "gpt-4o-mini"

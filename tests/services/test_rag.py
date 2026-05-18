"""Tests for app.services.rag.RAGService.

These tests cover every Phase 4 acceptance criterion:

* Grounded answer for an in-catalogue question.
* Polite refusal -- and **no AI call** -- for an off-topic question.
* Cache hit on the second identical call (no AI call, no usage record).
* Source schema: title, author, score only.
* Usage tracker invoked exactly once across two identical calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.vector_store import SearchResult
from app.prompts.rag import REFUSAL_MESSAGE
from app.services.rag import RAGAnswer, RAGService, SourceCitation

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeSettings:
    rag_top_k: int = 4
    rag_relevance_threshold: float = 0.35


def _make_generation_result(
    text: str = "In *Dune*, Frank Herbert tells the story of Arrakis...",
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    prompt_tokens: int | None = 120,
    completion_tokens: int | None = 60,
) -> MagicMock:
    """Build a stand-in for ``GenerationResult`` without coupling to its class."""
    result = MagicMock()
    result.text = text
    result.provider = provider
    result.model = model
    result.prompt_tokens = prompt_tokens
    result.completion_tokens = completion_tokens
    return result


def _make_ai_service(generation: MagicMock | None = None) -> MagicMock:
    svc = MagicMock()
    svc.model = "gpt-4o-mini"
    svc.generate = AsyncMock(return_value=generation or _make_generation_result())
    return svc


def _make_embedding_service(vector: list[float] | None = None) -> MagicMock:
    svc = MagicMock()
    svc.embed_one = AsyncMock(return_value=vector or [0.1, 0.2, 0.3])
    return svc


def _make_vector_store(results: list[SearchResult]) -> MagicMock:
    store = MagicMock()
    store.search = MagicMock(return_value=results)
    return store


def _make_cache(*, cached: Any | None = None) -> MagicMock:
    """Cache stand-in.  ``cached`` is returned by the first ``get`` only."""
    state: dict[str, Any] = {"value": cached}

    async def get(_key: str) -> Any:
        return state["value"]

    async def set_(key: str, value: Any, *, ttl: int | None = None) -> None:
        # Subsequent get() calls return the value just written so the
        # "second call hits cache" test exercises a realistic flow.
        state["value"] = value

    cache = MagicMock()
    cache.get = AsyncMock(side_effect=get)
    cache.set = AsyncMock(side_effect=set_)
    return cache


def _make_rate_limiter() -> MagicMock:
    limiter = MagicMock()
    limiter.acquire = AsyncMock(return_value=None)
    return limiter


def _make_usage_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.record = MagicMock(return_value=None)
    return tracker


def _make_search_result(
    *,
    book_id: str = "book-001",
    title: str = "Dune",
    author: str = "Frank Herbert",
    year: int = 1965,
    genre: str = "Science Fiction",
    description: str = "Arid desert planet Arrakis...",
    score: float = 0.87,
) -> SearchResult:
    return SearchResult(
        id=book_id,
        score=score,
        metadata={
            "title": title,
            "author": author,
            "year": year,
            "genre": genre,
            "description": description,
        },
    )


def _make_service(
    *,
    settings: _FakeSettings | None = None,
    ai_service: MagicMock | None = None,
    embedding_service: MagicMock | None = None,
    vector_store: MagicMock | None = None,
    cache: MagicMock | None = None,
    rate_limiter: MagicMock | None = None,
    usage_tracker: MagicMock | None = None,
) -> tuple[RAGService, dict[str, MagicMock]]:
    """Build a ``RAGService`` with all collaborators mocked.

    Returns the service and the dict of collaborators so tests can assert
    on them without rebuilding the fixtures.
    """
    ai_service = ai_service or _make_ai_service()
    embedding_service = embedding_service or _make_embedding_service()
    vector_store = vector_store or _make_vector_store([_make_search_result()])
    cache = cache or _make_cache(cached=None)
    rate_limiter = rate_limiter or _make_rate_limiter()
    usage_tracker = usage_tracker or _make_usage_tracker()

    service = RAGService(
        settings=settings or _FakeSettings(),  # type: ignore[arg-type]
        ai_service=ai_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        cache=cache,
        rate_limiter=rate_limiter,
        usage_tracker=usage_tracker,
    )
    return service, {
        "ai_service": ai_service,
        "embedding_service": embedding_service,
        "vector_store": vector_store,
        "cache": cache,
        "rate_limiter": rate_limiter,
        "usage_tracker": usage_tracker,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGroundedAnswer:
    @pytest.mark.anyio
    async def test_returns_grounded_answer_for_in_catalogue_question(self) -> None:
        """In-catalogue retrieval produces an answer that mentions a real book."""
        dune = _make_search_result(title="Dune", author="Frank Herbert", score=0.9)
        result = _make_generation_result(
            text="In *Dune*, Frank Herbert tells the story of Arrakis..."
        )
        ai_service = _make_ai_service(generation=result)
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=ai_service,
        )

        answer = await service.answer("desert planet stories?")

        assert isinstance(answer, RAGAnswer)
        assert "Dune" in answer.answer
        assert answer.cached is False
        ai_service.generate.assert_awaited_once()

    @pytest.mark.anyio
    async def test_sources_include_title_author_score_only(self) -> None:
        """SourceCitation must expose exactly title, author, score."""
        dune = _make_search_result(title="Dune", author="Frank Herbert", score=0.9)
        service, _collab = _make_service(vector_store=_make_vector_store([dune]))

        answer = await service.answer("desert planet stories?")

        assert len(answer.sources) == 1
        source = answer.sources[0]
        assert isinstance(source, SourceCitation)
        assert source.title == "Dune"
        assert source.author == "Frank Herbert"
        assert source.score == pytest.approx(0.9)
        # The dataclass slots prevent stray attributes from being added.
        assert source.__slots__ == ("title", "author", "score")  # type: ignore[attr-defined]

    @pytest.mark.anyio
    async def test_avg_relevance_is_mean_of_source_scores(self) -> None:
        results = [
            _make_search_result(book_id="a", title="A", score=0.9),
            _make_search_result(book_id="b", title="B", score=0.7),
        ]
        service, _collab = _make_service(vector_store=_make_vector_store(results))

        answer = await service.answer("anything")

        assert answer.avg_relevance == pytest.approx(0.8)


class TestRefusal:
    @pytest.mark.anyio
    async def test_returns_refusal_when_no_results_pass_threshold(self) -> None:
        """When nothing crosses the threshold, the answer is the REFUSAL_MESSAGE."""
        low = _make_search_result(score=0.1)  # below default threshold 0.35
        ai_service = _make_ai_service()
        usage_tracker = _make_usage_tracker()
        service, _collab = _make_service(
            vector_store=_make_vector_store([low]),
            ai_service=ai_service,
            usage_tracker=usage_tracker,
        )

        answer = await service.answer("what is the meaning of life?")

        assert answer.answer == REFUSAL_MESSAGE
        assert answer.sources == []
        assert answer.cached is False
        assert answer.avg_relevance == 0.0
        # Critical: refusal must skip the AI call entirely so a misbehaving
        # provider cannot fabricate an answer.
        ai_service.generate.assert_not_awaited()
        usage_tracker.record.assert_not_called()

    @pytest.mark.anyio
    async def test_returns_refusal_when_vector_store_empty(self) -> None:
        ai_service = _make_ai_service()
        service, _collab = _make_service(
            vector_store=_make_vector_store([]),
            ai_service=ai_service,
        )

        answer = await service.answer("anything")

        assert answer.answer == REFUSAL_MESSAGE
        assert answer.sources == []
        ai_service.generate.assert_not_awaited()


class TestCaching:
    @pytest.mark.anyio
    async def test_caches_response_on_second_call(self) -> None:
        """Second identical call returns cached=True without invoking the AI."""
        dune = _make_search_result(title="Dune", score=0.9)
        ai_service = _make_ai_service()
        cache = _make_cache(cached=None)  # cold cache; will be filled on first call
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=ai_service,
            cache=cache,
        )

        first = await service.answer("desert planet?")
        second = await service.answer("desert planet?")

        assert first.cached is False
        assert second.cached is True
        # AI called exactly once across both invocations.
        assert ai_service.generate.await_count == 1
        # Same answer text round-tripped through cache.
        assert second.answer == first.answer
        assert [(s.title, s.author, s.score) for s in second.sources] == [
            (s.title, s.author, s.score) for s in first.sources
        ]

    @pytest.mark.anyio
    async def test_cache_hit_bypasses_rate_limiter(self) -> None:
        """Cache hits must not consume rate-budget."""
        cached_payload = {
            "answer": "cached",
            "sources": [{"title": "T", "author": "A", "score": 0.5}],
            "avg_relevance": 0.5,
        }
        cache = _make_cache(cached=cached_payload)
        rate_limiter = _make_rate_limiter()
        ai_service = _make_ai_service()
        service, _collab = _make_service(
            cache=cache,
            rate_limiter=rate_limiter,
            ai_service=ai_service,
        )

        answer = await service.answer("anything")

        assert answer.cached is True
        rate_limiter.acquire.assert_not_awaited()
        ai_service.generate.assert_not_awaited()

    @pytest.mark.anyio
    async def test_normalised_cache_key_ignores_case_and_whitespace(self) -> None:
        """Trivially different phrasings hit the same cache entry."""
        dune = _make_search_result(score=0.9)
        ai_service = _make_ai_service()
        cache = _make_cache(cached=None)
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=ai_service,
            cache=cache,
        )

        await service.answer("Desert Planet?")
        await service.answer("  desert planet?  ")

        assert ai_service.generate.await_count == 1


class TestUsageTracking:
    @pytest.mark.anyio
    async def test_usage_tracker_called_only_for_non_cached(self) -> None:
        """Two identical calls produce exactly one usage record."""
        dune = _make_search_result(score=0.9)
        usage_tracker = _make_usage_tracker()
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            usage_tracker=usage_tracker,
        )

        await service.answer("desert planet?")
        await service.answer("desert planet?")

        assert usage_tracker.record.call_count == 1
        kwargs = usage_tracker.record.call_args.kwargs
        assert kwargs["operation"] == "generate"
        assert kwargs["provider"] == "openai"
        assert kwargs["prompt_tokens"] == 120
        assert kwargs["completion_tokens"] == 60

    @pytest.mark.anyio
    async def test_usage_tracker_handles_none_token_counts(self) -> None:
        """A provider that reports ``None`` tokens records ``0`` rather than crash."""
        dune = _make_search_result(score=0.9)
        result = _make_generation_result(prompt_tokens=None, completion_tokens=None)
        usage_tracker = _make_usage_tracker()
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=_make_ai_service(generation=result),
            usage_tracker=usage_tracker,
        )

        await service.answer("desert planet?")

        kwargs = usage_tracker.record.call_args.kwargs
        assert kwargs["prompt_tokens"] == 0
        assert kwargs["completion_tokens"] == 0


class TestPromptComposition:
    @pytest.mark.anyio
    async def test_system_prompt_passed_to_generate(self) -> None:
        """The RAG system prompt and tuned sampling params must reach the model."""
        from app.prompts.rag import RAG_MAX_TOKENS, RAG_SYSTEM_PROMPT, RAG_TEMPERATURE

        dune = _make_search_result(score=0.9)
        ai_service = _make_ai_service()
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=ai_service,
        )

        await service.answer("desert planet?")

        kwargs = ai_service.generate.call_args.kwargs
        assert kwargs["system"] == RAG_SYSTEM_PROMPT
        assert kwargs["temperature"] == RAG_TEMPERATURE
        assert kwargs["max_tokens"] == RAG_MAX_TOKENS

    @pytest.mark.anyio
    async def test_user_prompt_contains_context_and_question(self) -> None:
        dune = _make_search_result(title="Dune", author="Frank Herbert", score=0.9)
        ai_service = _make_ai_service()
        service, _collab = _make_service(
            vector_store=_make_vector_store([dune]),
            ai_service=ai_service,
        )

        await service.answer("What about desert planets?")

        prompt = ai_service.generate.call_args.args[0]
        assert "Dune" in prompt
        assert "Frank Herbert" in prompt
        assert "What about desert planets?" in prompt
        assert prompt.startswith("Context:")

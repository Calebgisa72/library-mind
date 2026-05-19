"""Tests for POST /search/books and POST /search/ask.

Roadmap testing requirements covered:
* test_search_books_returns_200_with_results
* test_ask_returns_cached_flag
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_embedding_service, get_rag_service, get_vector_store
from app.infrastructure.vector_store import SearchResult
from app.main import app
from app.services.rag import RAGAnswer, SourceCitation

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_embedding_service() -> MagicMock:
    svc = MagicMock()
    svc.embed_one = AsyncMock(return_value=[0.1] * 8)
    return svc


def _fake_vector_store(results: list[SearchResult] | None = None) -> MagicMock:
    vs = MagicMock()
    vs.search = MagicMock(
        return_value=(
            results
            if results is not None
            else [
                SearchResult(
                    id="book-dune",
                    score=0.87,
                    metadata={
                        "title": "Dune",
                        "author": "Frank Herbert",
                        "year": 1965,
                        "genre": "Science Fiction",
                    },
                )
            ]
        )
    )
    return vs


def _fake_rag_service(answer: RAGAnswer | None = None) -> MagicMock:
    svc = MagicMock()
    svc.answer = AsyncMock(
        return_value=answer
        or RAGAnswer(
            answer="In *Dune*, Frank Herbert explores the desert planet Arrakis.",
            sources=[SourceCitation(title="Dune", author="Frank Herbert", score=0.87)],
            cached=False,
            avg_relevance=0.87,
        )
    )
    return svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /search/books
# ---------------------------------------------------------------------------


class TestSearchBooks:
    def test_search_books_returns_200_with_results(self, client: TestClient) -> None:
        """Valid query returns 200 with a results list matching the API contract."""
        app.dependency_overrides[get_embedding_service] = lambda: _fake_embedding_service()
        app.dependency_overrides[get_vector_store] = lambda: _fake_vector_store()
        try:
            r = client.post("/search/books", json={"query": "desert planet adventure", "limit": 5})
            assert r.status_code == 200
            data = r.json()
            assert data["query"] == "desert planet adventure"
            assert len(data["results"]) == 1
            hit = data["results"][0]
            assert hit["id"] == "book-dune"
            assert hit["title"] == "Dune"
            assert hit["author"] == "Frank Herbert"
            assert hit["score"] == pytest.approx(0.87)
        finally:
            app.dependency_overrides.clear()

    def test_search_books_result_has_required_fields(self, client: TestClient) -> None:
        """Each result includes id, title, author, year, genre, score."""
        app.dependency_overrides[get_embedding_service] = lambda: _fake_embedding_service()
        app.dependency_overrides[get_vector_store] = lambda: _fake_vector_store()
        try:
            r = client.post("/search/books", json={"query": "fantasy quest"})
            assert r.status_code == 200
            hit = r.json()["results"][0]
            assert {"id", "title", "author", "year", "genre", "score"} == set(hit.keys())
        finally:
            app.dependency_overrides.clear()

    def test_search_books_empty_results_returns_empty_list(self, client: TestClient) -> None:
        app.dependency_overrides[get_embedding_service] = lambda: _fake_embedding_service()
        app.dependency_overrides[get_vector_store] = lambda: _fake_vector_store(results=[])
        try:
            r = client.post("/search/books", json={"query": "xyzzy nothing matches"})
            assert r.status_code == 200
            assert r.json()["results"] == []
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /search/ask
# ---------------------------------------------------------------------------


class TestAsk:
    def test_ask_returns_200_with_answer_and_sources(self, client: TestClient) -> None:
        """Valid question returns 200 with answer, sources, and cached flag."""
        app.dependency_overrides[get_rag_service] = lambda: _fake_rag_service()
        try:
            r = client.post(
                "/search/ask",
                json={"question": "What sci-fi books do you have about desert planets?"},
            )
            assert r.status_code == 200
            data = r.json()
            assert "answer" in data
            assert "sources" in data
            assert "cached" in data
            assert data["cached"] is False
            assert len(data["sources"]) == 1
            assert data["sources"][0]["title"] == "Dune"
        finally:
            app.dependency_overrides.clear()

    def test_ask_returns_cached_flag_true(self, client: TestClient) -> None:
        """When the service returns cached=True, the response reflects it."""
        cached = RAGAnswer(
            answer="In *Dune*...",
            sources=[SourceCitation(title="Dune", author="Frank Herbert", score=0.87)],
            cached=True,
            avg_relevance=0.87,
        )
        app.dependency_overrides[get_rag_service] = lambda: _fake_rag_service(cached)
        try:
            r = client.post(
                "/search/ask",
                json={"question": "What sci-fi books do you have about desert planets?"},
            )
            assert r.status_code == 200
            assert r.json()["cached"] is True
        finally:
            app.dependency_overrides.clear()

    def test_ask_source_schema_matches_api_reference(self, client: TestClient) -> None:
        """Each source has exactly title, author, score."""
        app.dependency_overrides[get_rag_service] = lambda: _fake_rag_service()
        try:
            r = client.post("/search/ask", json={"question": "Recommend a science fiction book."})
            assert r.status_code == 200
            source = r.json()["sources"][0]
            assert {"title", "author", "score"} == set(source.keys())
        finally:
            app.dependency_overrides.clear()

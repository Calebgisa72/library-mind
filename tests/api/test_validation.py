"""Tests for input validation and error handling across all API endpoints.

Roadmap testing requirements covered:
* test_empty_string_returns_422 — every endpoint
* test_rate_limit_returns_429 — exceed limit; assert status
* test_provider_failure_returns_503 — mock AllProvidersFailedError; assert status
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_chatbot_service,
    get_classifier_service,
    get_embedding_service,
    get_rag_service,
    get_summariser_service,
    get_vector_store,
)
from app.core.exceptions import AllProvidersFailedError, RateLimitExceededError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# 422 — Validation errors
# ---------------------------------------------------------------------------


class TestValidation422:
    def test_search_books_empty_query_returns_422(self, client: TestClient) -> None:
        """/search/books rejects a query shorter than 3 characters."""
        r = client.post("/search/books", json={"query": "ab"})
        assert r.status_code == 422

    def test_search_books_missing_query_returns_422(self, client: TestClient) -> None:
        """/search/books rejects a request with no query field."""
        r = client.post("/search/books", json={})
        assert r.status_code == 422

    def test_ask_empty_question_returns_422(self, client: TestClient) -> None:
        """/search/ask rejects a question shorter than 5 characters."""
        r = client.post("/search/ask", json={"question": "hi"})
        assert r.status_code == 422

    def test_ask_missing_question_returns_422(self, client: TestClient) -> None:
        """/search/ask rejects a request with no question field."""
        r = client.post("/search/ask", json={})
        assert r.status_code == 422

    def test_chat_missing_fields_returns_422(self, client: TestClient) -> None:
        """/chat rejects a request missing conversation_id or message."""
        r = client.post("/chat", json={"message": "Hello"})
        assert r.status_code == 422
        r2 = client.post("/chat", json={"conversation_id": "abc"})
        assert r2.status_code == 422

    def test_classify_empty_text_returns_422(self, client: TestClient) -> None:
        """/classify/ticket rejects text shorter than 5 characters."""
        r = client.post("/classify/ticket", json={"text": "ab"})
        assert r.status_code == 422

    def test_classify_missing_text_returns_422(self, client: TestClient) -> None:
        """/classify/ticket rejects a request with no text field."""
        r = client.post("/classify/ticket", json={})
        assert r.status_code == 422

    def test_summarise_empty_reviews_list_returns_422(self, client: TestClient) -> None:
        """/summarise/reviews rejects an empty reviews list."""
        r = client.post("/summarise/reviews", json={"reviews": []})
        assert r.status_code == 422

    def test_summarise_too_many_reviews_returns_422(self, client: TestClient) -> None:
        """/summarise/reviews rejects more than 50 reviews."""
        reviews = [f"Review {i} is a decent length text." for i in range(51)]
        r = client.post("/summarise/reviews", json={"reviews": reviews})
        assert r.status_code == 422

    def test_summarise_short_review_item_returns_422(self, client: TestClient) -> None:
        """/summarise/reviews rejects a review item shorter than 5 characters."""
        r = client.post("/summarise/reviews", json={"reviews": ["ok"]})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 429 — Rate limit
# ---------------------------------------------------------------------------


class TestRateLimit429:
    def test_rate_limit_returns_429_on_search_books(self, client: TestClient) -> None:
        """/search/books returns 429 when the service raises RateLimitExceededError."""
        svc = MagicMock()
        svc.embed_one = AsyncMock(side_effect=RateLimitExceededError())
        app.dependency_overrides[get_embedding_service] = lambda: svc

        vs = MagicMock()
        vs.search = MagicMock(return_value=[])
        app.dependency_overrides[get_vector_store] = lambda: vs
        try:
            r = client.post("/search/books", json={"query": "science fiction adventures"})
            assert r.status_code == 429
        finally:
            app.dependency_overrides.clear()

    def test_rate_limit_returns_429_on_ask(self, client: TestClient) -> None:
        """/search/ask returns 429 when the service raises RateLimitExceededError."""
        svc = MagicMock()
        svc.answer = AsyncMock(side_effect=RateLimitExceededError())
        app.dependency_overrides[get_rag_service] = lambda: svc
        try:
            r = client.post(
                "/search/ask",
                json={"question": "What sci-fi books do you have about space?"},
            )
            assert r.status_code == 429
        finally:
            app.dependency_overrides.clear()

    def test_rate_limit_returns_429_on_chat(self, client: TestClient) -> None:
        """/chat returns 429 when the service raises RateLimitExceededError."""
        svc = MagicMock()
        svc.reply = AsyncMock(side_effect=RateLimitExceededError())
        app.dependency_overrides[get_chatbot_service] = lambda: svc
        try:
            r = client.post(
                "/chat",
                json={"conversation_id": "c1", "message": "Hello there librarian"},
            )
            assert r.status_code == 429
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 503 — Provider failure
# ---------------------------------------------------------------------------


class TestProviderFailure503:
    def test_provider_failure_returns_503_on_ask(self, client: TestClient) -> None:
        """/search/ask returns 503 when AllProvidersFailedError is raised."""
        svc = MagicMock()
        svc.answer = AsyncMock(side_effect=AllProvidersFailedError())
        app.dependency_overrides[get_rag_service] = lambda: svc
        try:
            r = client.post(
                "/search/ask",
                json={"question": "What books do you have about the ocean?"},
            )
            assert r.status_code == 503
        finally:
            app.dependency_overrides.clear()

    def test_provider_failure_returns_503_on_chat(self, client: TestClient) -> None:
        """/chat returns 503 when AllProvidersFailedError is raised."""
        svc = MagicMock()
        svc.reply = AsyncMock(side_effect=AllProvidersFailedError())
        app.dependency_overrides[get_chatbot_service] = lambda: svc
        try:
            r = client.post(
                "/chat",
                json={"conversation_id": "c1", "message": "Recommend something good"},
            )
            assert r.status_code == 503
        finally:
            app.dependency_overrides.clear()

    def test_provider_failure_returns_503_on_classify(self, client: TestClient) -> None:
        """/classify/ticket returns 503 when AllProvidersFailedError is raised."""
        svc = MagicMock()
        svc.classify = AsyncMock(side_effect=AllProvidersFailedError())
        app.dependency_overrides[get_classifier_service] = lambda: svc
        try:
            r = client.post(
                "/classify/ticket",
                json={"text": "I cannot access my library account."},
            )
            assert r.status_code == 503
        finally:
            app.dependency_overrides.clear()

    def test_provider_failure_returns_503_on_summarise(self, client: TestClient) -> None:
        """/summarise/reviews returns 503 when AllProvidersFailedError is raised."""
        svc = MagicMock()
        svc.summarise = AsyncMock(side_effect=AllProvidersFailedError())
        app.dependency_overrides[get_summariser_service] = lambda: svc
        try:
            r = client.post(
                "/summarise/reviews",
                json={"reviews": ["This book was absolutely fantastic and well-written."]},
            )
            assert r.status_code == 503
        finally:
            app.dependency_overrides.clear()

    def test_provider_failure_response_has_detail(self, client: TestClient) -> None:
        """503 responses include a detail field in the body."""
        svc = MagicMock()
        svc.answer = AsyncMock(side_effect=AllProvidersFailedError("All providers down"))
        app.dependency_overrides[get_rag_service] = lambda: svc
        try:
            r = client.post(
                "/search/ask",
                json={"question": "Find me a book about mountains."},
            )
            assert r.status_code == 503
            assert "detail" in r.json()
        finally:
            app.dependency_overrides.clear()

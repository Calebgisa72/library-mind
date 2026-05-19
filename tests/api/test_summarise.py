"""Tests for POST /summarise/reviews.

Roadmap testing requirements covered:
* test_summarise_handles_1_to_50_reviews
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_summariser_service
from app.main import app
from app.services.summariser import ReviewSummary

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SAMPLE_SUMMARY = ReviewSummary(
    overall_sentiment="positive",
    estimated_rating=4.5,
    themes=["adventure", "world-building"],
    praise=["vivid descriptions", "complex characters"],
    criticism=["slow start"],
    recommendation="Recommended for fans of epic science fiction.",
)


def _fake_summariser(result: ReviewSummary | None = None) -> MagicMock:
    svc = MagicMock()
    svc.summarise = AsyncMock(return_value=result or _SAMPLE_SUMMARY)
    return svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /summarise/reviews
# ---------------------------------------------------------------------------


class TestSummariseReviews:
    def test_summarise_returns_200_with_summary(self, client: TestClient) -> None:
        """Valid review list returns 200 with a structured summary."""
        app.dependency_overrides[get_summariser_service] = lambda: _fake_summariser()
        try:
            r = client.post(
                "/summarise/reviews",
                json={"reviews": ["Absolutely loved this book!", "Great world-building."]},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["overall_sentiment"] == "positive"
            assert data["estimated_rating"] == pytest.approx(4.5)
            assert "themes" in data
            assert "praise" in data
            assert "criticism" in data
            assert "recommendation" in data
        finally:
            app.dependency_overrides.clear()

    def test_summarise_handles_1_review(self, client: TestClient) -> None:
        """A single review (minimum) is accepted and returns 200."""
        app.dependency_overrides[get_summariser_service] = lambda: _fake_summariser()
        try:
            r = client.post(
                "/summarise/reviews",
                json={"reviews": ["This book changed my life completely."]},
            )
            assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_summarise_handles_50_reviews(self, client: TestClient) -> None:
        """Exactly 50 reviews (maximum) is accepted and returns 200."""
        reviews = [f"Review number {i} for this wonderful book." for i in range(1, 51)]
        app.dependency_overrides[get_summariser_service] = lambda: _fake_summariser()
        try:
            r = client.post("/summarise/reviews", json={"reviews": reviews})
            assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_summarise_handles_1_to_50_reviews(self, client: TestClient) -> None:
        """Spot-check a range of review counts (1, 10, 25, 50) all return 200."""
        for n in (1, 10, 25, 50):
            reviews = [f"Review {i}: This book is quite interesting." for i in range(1, n + 1)]
            app.dependency_overrides[get_summariser_service] = lambda: _fake_summariser()
            try:
                r = client.post("/summarise/reviews", json={"reviews": reviews})
                assert r.status_code == 200, f"Expected 200 for {n} reviews, got {r.status_code}"
            finally:
                app.dependency_overrides.clear()

    def test_summarise_response_schema(self, client: TestClient) -> None:
        """Response has all required summary fields."""
        app.dependency_overrides[get_summariser_service] = lambda: _fake_summariser()
        try:
            r = client.post(
                "/summarise/reviews",
                json={"reviews": ["Great read with beautiful prose."]},
            )
            assert r.status_code == 200
            keys = set(r.json().keys())
            assert {
                "overall_sentiment",
                "estimated_rating",
                "themes",
                "praise",
                "criticism",
                "recommendation",
            }.issubset(keys)
        finally:
            app.dependency_overrides.clear()

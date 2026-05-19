"""Tests for POST /classify/ticket.

Roadmap testing requirements covered:
* test_classify_returns_structured_json
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_classifier_service
from app.main import app
from app.services.classifier import TicketClassification

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SAMPLE_CLASSIFICATION = TicketClassification(
    category="technical",
    priority="high",
    sentiment="negative",
    department="IT Support",
    summary="User cannot log into the library portal.",
)


def _fake_classifier(result: TicketClassification | None = None) -> MagicMock:
    svc = MagicMock()
    svc.classify = AsyncMock(return_value=result or _SAMPLE_CLASSIFICATION)
    return svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /classify/ticket
# ---------------------------------------------------------------------------


class TestClassifyTicket:
    def test_classify_returns_structured_json(self, client: TestClient) -> None:
        """Valid ticket text returns 200 with all classification fields."""
        app.dependency_overrides[get_classifier_service] = lambda: _fake_classifier()
        try:
            r = client.post(
                "/classify/ticket",
                json={"text": "I cannot log in to my library account since yesterday."},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["category"] == "technical"
            assert data["priority"] == "high"
            assert data["sentiment"] == "negative"
            assert "department" in data
            assert "summary" in data
        finally:
            app.dependency_overrides.clear()

    def test_classify_response_schema(self, client: TestClient) -> None:
        """Response has exactly category, priority, sentiment, department, summary."""
        app.dependency_overrides[get_classifier_service] = lambda: _fake_classifier()
        try:
            r = client.post("/classify/ticket", json={"text": "My book is overdue."})
            assert r.status_code == 200
            assert {"category", "priority", "sentiment", "department", "summary"} == set(
                r.json().keys()
            )
        finally:
            app.dependency_overrides.clear()

    def test_classify_all_categories_accepted(self, client: TestClient) -> None:
        """Any of the six valid category values is accepted and round-trips correctly."""
        for category in ("account", "borrowing", "technical", "complaint", "suggestion", "general"):
            classification = TicketClassification(
                category=category,  # type: ignore[arg-type]
                priority="low",
                sentiment="neutral",
                department="General",
                summary="Test summary.",
            )
            app.dependency_overrides[get_classifier_service] = (
                lambda c=classification: _fake_classifier(c)
            )
            try:
                r = client.post("/classify/ticket", json={"text": "Some ticket text here."})
                assert r.status_code == 200
                assert r.json()["category"] == category
            finally:
                app.dependency_overrides.clear()

"""Tests for GET /health.

Roadmap testing requirements covered:
* test_health_returns_daily_cost_and_request_count
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_cache, get_usage_tracker
from app.main import app

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_cache(*, connected: bool = True) -> MagicMock:
    cache = MagicMock()
    cache.ping = AsyncMock(return_value=connected)
    return cache


def _fake_usage_tracker(*, daily_cost: float = 0.05, request_count: int = 12) -> MagicMock:
    tracker = MagicMock()
    tracker.daily_cost_usd = MagicMock(return_value=daily_cost)
    tracker.total_requests_today = MagicMock(return_value=request_count)
    return tracker


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        """Health check returns 200 with status ok."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache()
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker()
        try:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
        finally:
            app.dependency_overrides.clear()

    def test_health_returns_daily_cost_and_request_count(self, client: TestClient) -> None:
        """Health response includes daily_cost_usd and request_count_today."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache()
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker(
            daily_cost=1.23, request_count=42
        )
        try:
            r = client.get("/health")
            assert r.status_code == 200
            data = r.json()
            assert data["daily_cost_usd"] == pytest.approx(1.23)
            assert data["request_count_today"] == 42
        finally:
            app.dependency_overrides.clear()

    def test_health_cache_connected(self, client: TestClient) -> None:
        """When Redis ping succeeds, cache field is 'connected'."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache(connected=True)
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker()
        try:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["cache"] == "connected"
        finally:
            app.dependency_overrides.clear()

    def test_health_cache_unavailable(self, client: TestClient) -> None:
        """When Redis ping fails, cache field is 'unavailable'."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache(connected=False)
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker()
        try:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["cache"] == "unavailable"
        finally:
            app.dependency_overrides.clear()

    def test_health_response_schema(self, client: TestClient) -> None:
        """Response includes all expected fields."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache()
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker()
        try:
            r = client.get("/health")
            assert r.status_code == 200
            keys = set(r.json().keys())
            assert {
                "status",
                "version",
                "providers",
                "cache",
                "daily_cost_usd",
                "daily_budget_usd",
                "request_count_today",
            }.issubset(keys)
        finally:
            app.dependency_overrides.clear()

    def test_health_providers_field(self, client: TestClient) -> None:
        """The providers dict contains openai, anthropic, and amaliai keys."""
        app.dependency_overrides[get_cache] = lambda: _fake_cache()
        app.dependency_overrides[get_usage_tracker] = lambda: _fake_usage_tracker()
        try:
            r = client.get("/health")
            assert r.status_code == 200
            providers = r.json()["providers"]
            assert "openai" in providers
            assert "anthropic" in providers
            assert "amaliai" in providers
        finally:
            app.dependency_overrides.clear()

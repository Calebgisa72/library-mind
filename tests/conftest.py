"""Shared pytest fixtures.

Phase 0 leaves this file intentionally minimal. Concrete fixtures
(test client, settings overrides, in-memory cache, fake AI provider)
will be added alongside the modules they exercise in later phases.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Force pytest-asyncio / anyio to use asyncio (no trio in this project)."""
    return "asyncio"

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


@pytest.fixture(autouse=True)
def _clear_socks_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove SOCKS-based proxy env vars that cause ImportError in test envs.

    The Linux CI/sandbox environment may export grpc_proxy or ftp_proxy with
    a socks5h:// scheme.  httpx picks these up and tries to create a SOCKS
    transport, which requires the optional 'socksio' package.  Since all AI
    provider tests mock the HTTP layer anyway, clearing these vars makes no
    difference to test behaviour while preventing the spurious ImportError.
    """
    for var in ("grpc_proxy", "ftp_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)

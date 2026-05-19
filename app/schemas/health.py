"""Pydantic response schema for GET /health.

The health endpoint never makes a paid AI call; it reads in-memory counters
only.  ``status`` is ``"ok"`` when at least one provider is configured and
the application has not entered a degraded state.  ``cache`` is
``"connected"`` or ``"unavailable"`` based on a live Redis ping.
``daily_budget_usd`` is ``None`` when ``BUDGET_DAILY_LIMIT_USD`` is ``0.0``
(cap disabled) and a positive float otherwise.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response payload for ``GET /health``."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    version: str
    providers: dict[str, str]
    cache: Literal["connected", "unavailable"]
    daily_cost_usd: float
    daily_budget_usd: float | None
    request_count_today: int


__all__ = ["HealthResponse"]

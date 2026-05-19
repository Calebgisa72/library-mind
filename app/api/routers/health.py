"""Router for the operational health check endpoint.

Endpoint
--------
GET /health
    Return the application status, provider configuration, Redis cache
    reachability, daily spend, and request count.  Never makes a paid AI
    call — reads in-memory counters only.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from app import __version__
from app.api.dependencies import get_cache, get_usage_tracker
from app.core.settings import Settings, get_settings
from app.infrastructure.cache import Cache
from app.infrastructure.usage_tracker import UsageTracker
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
    description=(
        "Return current application status, provider availability, Redis connectivity, "
        "daily spend in USD, and total request count for today."
    ),
)
async def health(
    settings: Settings = Depends(get_settings),
    cache: Cache = Depends(get_cache),
    usage_tracker: UsageTracker = Depends(get_usage_tracker),
) -> HealthResponse:
    """Read in-memory counters and ping Redis; return the health envelope."""
    cache_status: Literal["connected", "unavailable"] = (
        "connected" if await cache.ping() else "unavailable"
    )

    providers: dict[str, str] = {
        name: ("configured" if settings._has_key(name) else "not_configured")  # type: ignore[arg-type]
        for name in ("openai", "anthropic", "amaliai")
    }

    daily_cost = usage_tracker.daily_cost_usd()
    request_count = usage_tracker.total_requests_today()

    # A zero budget limit means the cap is disabled; surface None so clients
    # know there is no effective ceiling rather than showing a zero ceiling.
    daily_budget: float | None = settings.budget_daily_limit_usd or None

    return HealthResponse(
        status="ok",
        version=__version__,
        providers=providers,
        cache=cache_status,
        daily_cost_usd=daily_cost,
        daily_budget_usd=daily_budget,
        request_count_today=request_count,
    )

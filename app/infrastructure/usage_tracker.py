"""In-memory usage tracker: token counting and USD cost estimation.

Every AI call records a :class:`UsageRecord` that captures the provider,
model, operation type, token counts, and estimated cost in USD.  The
:class:`UsageTracker` aggregates these records and exposes daily totals
consumed by the ``/health`` endpoint.

Pricing table
-------------
``PRICING`` maps ``(provider, model)`` to ``(input_usd_per_1k,
output_usd_per_1k)``.  Only models actually used by this lab are listed;
unknown models default to ``(0.0, 0.0)`` (free / unknown).  Update the
table when vendor prices change -- it is the single place in the codebase
where pricing lives.

Token counting
--------------
The providers already report token counts in :class:`~app.providers.base.GenerationResult`.
If a provider does not report counts (``None``), the caller should pass ``0``
for that field; the tracker logs the record but the cost will be understated.
Using ``tiktoken`` for accurate counting when providers omit usage data is a
future enhancement documented in ``docs/ARCHITECTURE.md`` Section *Cost
Management*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pricing table: (provider, model) -> (input_usd_per_1k, output_usd_per_1k)
# ---------------------------------------------------------------------------
# Update here when vendors change their prices; nowhere else in the codebase
# should contain pricing constants.  Unknown models cost $0.00 (see record()).

PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),
    ("openai", "gpt-4o"): (0.0025, 0.01),
    ("openai", "text-embedding-3-small"): (0.00002, 0.0),
    ("openai", "text-embedding-3-large"): (0.00013, 0.0),
    ("openai", "text-embedding-ada-002"): (0.00010, 0.0),
    # Anthropic
    ("anthropic", "claude-3-5-haiku-latest"): (0.0008, 0.004),
    ("anthropic", "claude-3-5-sonnet-latest"): (0.003, 0.015),
    ("anthropic", "claude-3-haiku-20240307"): (0.00025, 0.00125),
    # AmaliAI: training credits -- billed at $0 for lab purposes.
    # Add a real entry here if the provider publishes a price.
}


# ---------------------------------------------------------------------------
# UsageRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Immutable record of a single AI call.

    Attributes
    ----------
    timestamp:
        UTC datetime of the call.
    provider:
        Provider identifier (``"openai"``, ``"anthropic"``, ``"amaliai"``).
    model:
        Model identifier as reported by the provider.
    operation:
        ``"generate"`` or ``"embed"``.
    prompt_tokens:
        Input tokens consumed.  Use ``0`` when the provider did not report.
    completion_tokens:
        Output tokens generated.  Always ``0`` for embedding calls.
    cost_usd:
        Estimated USD cost derived from :data:`PRICING`.  Zero when the
        model is not in the pricing table.
    """

    timestamp: datetime
    provider: str
    model: str
    operation: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# ---------------------------------------------------------------------------
# UsageTracker
# ---------------------------------------------------------------------------


class UsageTracker:
    """In-memory accumulator of AI call usage records.

    Thread-safety note: the ``_records`` list is appended to by
    :meth:`record` which is called from async request handlers.  In
    CPython, ``list.append`` is atomic under the GIL, so concurrent appends
    are safe.  This would not hold across processes; a production
    implementation would use Redis or a database.
    """

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> UsageRecord:
        """Create a :class:`UsageRecord`, log it, and store it in memory.

        Cost is computed from :data:`PRICING`.  Models not in the table
        are silently recorded at ``$0.00`` so unknown providers (e.g.
        AmaliAI training credits) do not break the tracker.

        Parameters
        ----------
        provider:
            Provider identifier (``"openai"``, ``"anthropic"``, etc.).
        model:
            Exact model string as returned by the provider SDK.
        operation:
            ``"generate"`` or ``"embed"``.
        prompt_tokens:
            Number of input tokens billed by the provider.
        completion_tokens:
            Number of output tokens generated (``0`` for embeddings).

        Returns
        -------
        UsageRecord
            The newly created, appended record.
        """
        input_per_1k, output_per_1k = PRICING.get((provider, model), (0.0, 0.0))
        cost = (prompt_tokens / 1000.0) * input_per_1k + (
            completion_tokens / 1000.0
        ) * output_per_1k

        rec = UsageRecord(
            timestamp=datetime.now(tz=timezone.utc),
            provider=provider,
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        )
        self._records.append(rec)
        log.info(
            "usage.recorded",
            provider=provider,
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 8),
        )
        return rec

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def daily_cost_usd(self, *, day: date | None = None) -> float:
        """Return the total cost in USD for all records on *day*.

        Parameters
        ----------
        day:
            UTC date to aggregate.  Defaults to today (UTC).

        Returns
        -------
        float
            Sum of ``cost_usd`` for all matching records.  Returns ``0.0``
            when there are no records for that day.
        """
        target = day or datetime.now(tz=timezone.utc).date()
        return sum(r.cost_usd for r in self._records if r.timestamp.date() == target)

    def total_requests_today(self) -> int:
        """Return the count of AI calls recorded today (UTC)."""
        today = datetime.now(tz=timezone.utc).date()
        return sum(1 for r in self._records if r.timestamp.date() == today)

    def all_records(self) -> list[UsageRecord]:
        """Return a snapshot of all stored records (oldest first).

        Returns a copy so callers cannot mutate internal state.
        """
        return list(self._records)

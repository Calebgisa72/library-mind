"""Tests for app.infrastructure.usage_tracker."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.infrastructure.usage_tracker import PRICING, UsageRecord, UsageTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(
    tracker: UsageTracker,
    *,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    operation: str = "generate",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> UsageRecord:
    return tracker.record(
        provider=provider,
        model=model,
        operation=operation,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


# ---------------------------------------------------------------------------
# UsageRecord (dataclass sanity)
# ---------------------------------------------------------------------------

class TestUsageRecord:
    def test_is_frozen_dataclass(self) -> None:
        rec = UsageRecord(
            timestamp=datetime.now(tz=timezone.utc),
            provider="openai",
            model="gpt-4o-mini",
            operation="generate",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.0,
        )
        with pytest.raises(Exception):   # FrozenInstanceError
            rec.prompt_tokens = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# UsageTracker.record()
# ---------------------------------------------------------------------------

class TestUsageTrackerRecord:
    def test_record_returns_usage_record(self) -> None:
        tracker = UsageTracker()
        rec = _record(tracker)
        assert isinstance(rec, UsageRecord)

    def test_record_computes_correct_cost_for_gpt4o_mini(self) -> None:
        """Acceptance-criterion verification:
        prompt=100, completion=50, model=gpt-4o-mini
        cost = 100/1000*0.00015 + 50/1000*0.0006 = 0.000045
        """
        tracker = UsageTracker()
        rec = tracker.record(
            provider="openai",
            model="gpt-4o-mini",
            operation="generate",
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert abs(rec.cost_usd - 0.000045) < 1e-10

    def test_record_cost_zero_for_unknown_model(self) -> None:
        tracker = UsageTracker()
        rec = tracker.record(
            provider="amaliai",
            model="some-unknown-model",
            operation="generate",
            prompt_tokens=500,
            completion_tokens=200,
        )
        assert rec.cost_usd == 0.0

    def test_record_stores_in_memory(self) -> None:
        tracker = UsageTracker()
        assert len(tracker.all_records()) == 0
        _record(tracker)
        assert len(tracker.all_records()) == 1
        _record(tracker)
        assert len(tracker.all_records()) == 2

    def test_record_timestamps_are_utc(self) -> None:
        tracker = UsageTracker()
        rec = _record(tracker)
        assert rec.timestamp.tzinfo is not None
        assert rec.timestamp.tzinfo == timezone.utc

    def test_record_preserves_all_fields(self) -> None:
        tracker = UsageTracker()
        rec = tracker.record(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            operation="embed",
            prompt_tokens=20,
            completion_tokens=0,
        )
        assert rec.provider == "anthropic"
        assert rec.model == "claude-3-5-haiku-latest"
        assert rec.operation == "embed"
        assert rec.prompt_tokens == 20
        assert rec.completion_tokens == 0

    def test_embedding_cost_only_input_tokens(self) -> None:
        """Embedding calls have no completion tokens."""
        tracker = UsageTracker()
        rec = tracker.record(
            provider="openai",
            model="text-embedding-3-small",
            operation="embed",
            prompt_tokens=1000,
            completion_tokens=0,
        )
        # 1000/1000 * 0.00002 = 0.00002
        assert abs(rec.cost_usd - 0.00002) < 1e-10

    def test_anthropic_haiku_cost(self) -> None:
        tracker = UsageTracker()
        rec = tracker.record(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            operation="generate",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        # 1000/1000*0.0008 + 500/1000*0.004 = 0.0008 + 0.002 = 0.0028
        assert abs(rec.cost_usd - 0.0028) < 1e-10


# ---------------------------------------------------------------------------
# UsageTracker.daily_cost_usd()
# ---------------------------------------------------------------------------

class TestDailyCostUsd:
    def test_returns_zero_with_no_records(self) -> None:
        assert UsageTracker().daily_cost_usd() == 0.0

    def test_sums_all_records_for_today(self) -> None:
        tracker = UsageTracker()
        _record(tracker, prompt_tokens=100, completion_tokens=50)   # 0.000045
        _record(tracker, prompt_tokens=100, completion_tokens=50)   # 0.000045
        cost = tracker.daily_cost_usd()
        assert abs(cost - 0.000090) < 1e-10

    def test_cost_is_non_zero_after_ai_call(self) -> None:
        """Acceptance criterion: usage tracker reports non-zero cost after AI call."""
        tracker = UsageTracker()
        _record(tracker, prompt_tokens=10, completion_tokens=5)
        assert tracker.daily_cost_usd() > 0.0

    def test_filters_by_specific_day(self) -> None:
        tracker = UsageTracker()
        # Inject a record for yesterday by mutating after creation
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        old_rec = UsageRecord(
            timestamp=yesterday,
            provider="openai",
            model="gpt-4o-mini",
            operation="generate",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.000045,
        )
        tracker._records.append(old_rec)
        _record(tracker)   # today's record

        today = datetime.now(tz=timezone.utc).date()
        assert abs(tracker.daily_cost_usd(day=today) - 0.000045) < 1e-10
        assert tracker.daily_cost_usd(day=yesterday.date()) == 0.000045

    def test_excludes_other_days(self) -> None:
        tracker = UsageTracker()
        future = datetime.now(tz=timezone.utc) + timedelta(days=5)
        future_rec = UsageRecord(
            timestamp=future,
            provider="openai",
            model="gpt-4o-mini",
            operation="generate",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=99.0,
        )
        tracker._records.append(future_rec)
        # Today has no records -> cost is 0
        assert tracker.daily_cost_usd() == 0.0


# ---------------------------------------------------------------------------
# UsageTracker.total_requests_today()
# ---------------------------------------------------------------------------

class TestTotalRequestsToday:
    def test_zero_with_no_records(self) -> None:
        assert UsageTracker().total_requests_today() == 0

    def test_counts_all_records_today(self) -> None:
        tracker = UsageTracker()
        _record(tracker)
        _record(tracker)
        _record(tracker)
        assert tracker.total_requests_today() == 3

    def test_excludes_yesterday(self) -> None:
        tracker = UsageTracker()
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        old_rec = UsageRecord(
            timestamp=yesterday,
            provider="openai",
            model="gpt-4o-mini",
            operation="generate",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.0,
        )
        tracker._records.append(old_rec)
        _record(tracker)  # one today
        assert tracker.total_requests_today() == 1


# ---------------------------------------------------------------------------
# PRICING table sanity
# ---------------------------------------------------------------------------

class TestPricingTable:
    def test_gpt4o_mini_entry_exists(self) -> None:
        assert ("openai", "gpt-4o-mini") in PRICING

    def test_embedding_model_entry_exists(self) -> None:
        assert ("openai", "text-embedding-3-small") in PRICING

    def test_anthropic_haiku_entry_exists(self) -> None:
        assert ("anthropic", "claude-3-5-haiku-latest") in PRICING

    def test_all_entries_have_non_negative_prices(self) -> None:
        for key, (inp, out) in PRICING.items():
            assert inp >= 0.0, f"{key} has negative input price"
            assert out >= 0.0, f"{key} has negative output price"

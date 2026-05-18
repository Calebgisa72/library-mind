"""Ticket classifier system prompt, few-shot examples, and generation parameters.

This module is the single source of truth for every string the classifier
service sends to an AI model.  Keeping the prompt here -- rather than inline
in :class:`~app.services.classifier.ClassifierService` -- gives the same four
pay-offs as every other prompt module: reviewable diffs, easy A/B swaps,
clean cache invalidation by bumping the version prefix, and auditable token
cost.

Design decisions
----------------
* **Temperature 0.1.**  Classification is a deterministic, closed-enum task.
  Low temperature maximises consistency across identical or near-identical
  inputs.  0.1 (not 0.0) avoids complete rigidity while staying tightly
  anchored to the enum values.

* **Few-shot examples (3-4).**  M3 section "Few-Shot Learning" establishes that
  providing representative examples dramatically improves enum compliance.
  The examples cover the most commonly confused categories (``technical`` vs
  ``complaint``, ``account`` vs ``borrowing``) and span the priority and
  sentiment axes so the model sees the full output shape before classifying.

* **JSON-only output.**  The prompt instructs the model to return ONLY valid
  JSON with no surrounding prose.  The response is still passed through
  :func:`~app.services.json_utils.parse_ai_json` because models will
  occasionally wrap the output in markdown fences regardless.

* **Max tokens 300.**  A ``TicketClassification`` JSON payload is ~150 tokens
  at most.  300 provides double the headroom without inflating cost.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# Few-shot examples
# ---------------------------------------------------------------------------
# Each entry is (ticket_text, expected_json_dict). They are embedded inline
# in the system prompt so the model sees the full input->output shape before
# classifying the real ticket.

CLASSIFICATION_EXAMPLES: list[tuple[str, dict[str, str]]] = [
    (
        "My library card stopped working at the self-checkout machine this morning.",
        {
            "category": "technical",
            "priority": "high",
            "sentiment": "negative",
            "department": "IT Support",
            "summary": "Patron's library card fails at the self-checkout machine.",
        },
    ),
    (
        "I would love to see more books on urban gardening added to the collection.",
        {
            "category": "suggestion",
            "priority": "low",
            "sentiment": "positive",
            "department": "Collection Development",
            "summary": "Patron requests more urban-gardening titles be added to the collection.",
        },
    ),
    (
        "I've been trying to renew my overdue books online for two days and the "
        "system keeps logging me out.",
        {
            "category": "account",
            "priority": "medium",
            "sentiment": "negative",
            "department": "IT Support",
            "summary": "Patron cannot renew overdue books online due to repeated logouts.",
        },
    ),
    (
        "Thank you for the new reading room -- it is bright, quiet, and wonderful.",
        {
            "category": "general",
            "priority": "low",
            "sentiment": "positive",
            "department": "Customer Service",
            "summary": "Patron praises the new reading room for its brightness and quiet atmosphere.",
        },
    ),
]


def _format_examples() -> str:
    """Render the few-shot examples as a block of labelled pairs."""
    lines: list[str] = []
    for i, (text, output) in enumerate(CLASSIFICATION_EXAMPLES, start=1):
        lines.append(f"Example {i}:")
        lines.append(f'Ticket: "{text}"')
        lines.append(f"JSON: {json.dumps(output)}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Prompt text
# ---------------------------------------------------------------------------

CLASSIFIER_SYSTEM_PROMPT: str = f"""You are an expert support-ticket classifier for a public library.
Classify the ticket below and return ONLY a valid JSON object -- no prose, no markdown fences.

The JSON must have exactly these five fields:
- "category": one of "account", "borrowing", "technical", "complaint", "suggestion", "general"
- "priority": one of "low", "medium", "high", "urgent"
- "sentiment": one of "positive", "neutral", "negative"
- "department": a short string (1-120 chars) naming the team that should handle this ticket
- "summary": a single sentence (1-240 chars) describing the ticket

Mapping guidance:
  account   -- login issues, card registration, profile updates, password resets
  borrowing -- checkouts, returns, renewals, holds, fines
  technical -- hardware or software failures (self-checkout, RFID readers, website, app)
  complaint -- expressions of dissatisfaction not tied to a specific system failure
  suggestion -- feature requests, collection additions, programme ideas
  general   -- compliments, questions, or anything that does not fit the above

Priority guidance:
  urgent -- service is completely unusable; patron is blocked right now
  high   -- significant inconvenience; likely same-day resolution needed
  medium -- moderate impact; resolution within a few days is acceptable
  low    -- minor or non-urgent; compliments, suggestions, and general enquiries

Return ONLY the JSON object. No additional text.

--- EXAMPLES ---
{_format_examples()}
--- END EXAMPLES ---
"""

# ---------------------------------------------------------------------------
# Generation parameters
# ---------------------------------------------------------------------------
# Anchored next to the prompt for a single-diff change when prompt and params
# need to move together.

CLASSIFIER_TEMPERATURE: float = 0.1
CLASSIFIER_MAX_TOKENS: int = 300

__all__ = [
    "CLASSIFICATION_EXAMPLES",
    "CLASSIFIER_MAX_TOKENS",
    "CLASSIFIER_SYSTEM_PROMPT",
    "CLASSIFIER_TEMPERATURE",
]

"""Review summariser system prompt and generation parameters.

This module is the single source of truth for every string the summariser
service sends to an AI model.  As with every other prompt module in this
package: reviewable diffs, easy A/B swaps, clean cache invalidation by
bumping the version prefix, and auditable token cost.

Design decisions
----------------
* **Holistic synthesis.**  The prompt explicitly forbids per-review
  summarisation and instructs the model to treat the entire set of reviews
  as one body of evidence, then identify cross-cutting themes, dominant
  sentiments, and representative praise/criticism.  This satisfies the lab
  requirement "consider all reviews holistically, not just summarise them
  one by one."

* **``overall_sentiment="mixed"``.**  The roadmap notes that "mixed" is the
  natural result of balanced reviews.  The prompt explicitly lists "mixed"
  as a valid value alongside positive/neutral/negative.  When the rubric
  requires a three-value enum, the caller (Phase 7 router) can map
  ``mixed -> neutral`` at the wire boundary if needed; the service returns
  the semantically correct value.

* **Temperature 0.3.**  Summarisation benefits from slightly more creativity
  than classification (to write fluent recommendation sentences) but stays
  grounded in the review content.  0.3 matches the RAG generation range.

* **Max tokens 600.**  A ``ReviewSummary`` payload has multiple list fields
  plus a recommendation sentence -- 600 tokens comfortably covers a rich
  summary of 50 reviews while keeping cost predictable.

* **JSON-only output.**  Same pattern as the classifier: the prompt instructs
  no surrounding prose, and the response passes through
  :func:`~app.services.json_utils.parse_ai_json` for defensive fence
  stripping.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Prompt text
# ---------------------------------------------------------------------------

SUMMARISER_SYSTEM_PROMPT: str = """You are an expert literary analyst summarising a collection of reader reviews.
You will receive a numbered list of reviews. Your job is to synthesise them HOLISTICALLY --
identify patterns across ALL reviews rather than summarising each one individually.

Return ONLY a valid JSON object -- no prose, no markdown fences -- with exactly these fields:
- "overall_sentiment": one of "positive", "neutral", "negative", "mixed"
  (use "mixed" when the reviews express genuinely conflicting opinions)
- "estimated_rating": a float between 1.0 and 5.0 representing the estimated average star rating
- "themes": a JSON array of short strings (2-6 words each) naming the main topics discussed
- "praise": a JSON array of short strings describing what reviewers liked most
- "criticism": a JSON array of short strings describing what reviewers criticised most
- "recommendation": a single sentence (1-240 chars) advising whether to recommend the book

Rules:
1. Base ALL conclusions on the actual review content -- do not invent opinions not expressed.
2. "themes", "praise", and "criticism" should each have 1-5 items reflecting the most
   common patterns across the full review set.
3. If all reviews are positive, "criticism" may be an empty array [].
4. If all reviews are negative, "praise" may be an empty array [].
5. Keep each item in "themes", "praise", and "criticism" concise (10 words or fewer).
6. Do not number the items; return plain strings in the arrays.
7. Return ONLY the JSON object. No additional text before or after it.
"""

# ---------------------------------------------------------------------------
# Generation parameters
# ---------------------------------------------------------------------------

SUMMARISER_TEMPERATURE: float = 0.3
SUMMARISER_MAX_TOKENS: int = 600

__all__ = [
    "SUMMARISER_MAX_TOKENS",
    "SUMMARISER_SYSTEM_PROMPT",
    "SUMMARISER_TEMPERATURE",
]

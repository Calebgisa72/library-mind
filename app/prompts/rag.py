"""RAG system prompt, refusal message, and context formatter.

This module is the single source of truth for every string the RAG service
sends to an AI model.  Keeping the prompt here -- rather than as a
triple-quoted string buried inside ``RAGService`` -- gives us four practical
pay-off:

1. **PR review**: a prompt change shows up as a diff in a single, named file.
2. **A/B testing**: swapping the constant is a one-import-line change.
3. **Cache invalidation**: bumping the cache-key version prefix
   (``v1:rag:...`` -> ``v2:rag:...``) cleanly invalidates stale responses.
4. **Token accounting**: the prompt's token cost is auditable in one place.

The prompt is intentionally short and rule-based: it gives the model exactly
one job ("answer using only the context") and exactly one fallback
("reply verbatim with the refusal sentence").  ``REFUSAL_MESSAGE`` is also
returned **deterministically** -- without any AI call -- when retrieval
finds nothing above the relevance threshold, so the off-topic acceptance
criterion passes reliably regardless of provider behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.infrastructure.vector_store import SearchResult


# ---------------------------------------------------------------------------
# Prompt text
# ---------------------------------------------------------------------------

RAG_SYSTEM_PROMPT: str = """You are a warm, knowledgeable librarian at a public library.
Answer the patron's question using ONLY the books provided in the context below. Those
books have already been selected as the most relevant matches in our catalogue, so treat
them as your available shelf.

Follow these rules without exception:

1. Be helpful and specific. Recommend and discuss the books that best fit the patron's
   request, citing each one by its exact title (e.g. "In *Dune*, ..."). If no single
   book is a perfect match, recommend the closest relevant titles from the context and
   briefly explain the connection rather than refusing.
2. Use ONLY the books in the context. Never invent or mention titles, authors, or facts
   that are not present in the context.
3. Reply verbatim with "I'm sorry, I couldn't find that information in our catalogue."
   ONLY when the context is empty or none of the provided books are even loosely related
   to the question.
4. Keep the tone warm, concise, and welcoming -- two to four sentences. Do not mention
   being an AI.
"""


REFUSAL_MESSAGE: str = "I'm sorry, I couldn't find that information in our catalogue."


# ---------------------------------------------------------------------------
# Generation parameters
# ---------------------------------------------------------------------------
# Anchored next to the prompt that uses them so a future prompt rewrite that
# warrants different sampling settings can adjust both in one diff.
# 0.3 is low enough to stay grounded in the retrieved context but high enough
# to read fluently. 512 tokens fits the "two to four sentences" guidance with
# comfortable headroom for longer multi-source answers.

RAG_TEMPERATURE: float = 0.3
RAG_MAX_TOKENS: int = 512


# ---------------------------------------------------------------------------
# Context block formatting
# ---------------------------------------------------------------------------


def format_context(results: Iterable[SearchResult]) -> str:
    """Render retrieved books as a numbered context block for the prompt.

    Each entry is formatted as::

        [N] Title by Author (Year, Genre): description

    Numbering makes it easy for the model to cite a specific source by index
    if it chooses (and for a future enhancement to map citations back to
    ``SearchResult`` records).  The format is deliberately stable: tests
    snapshot it, and any change should be made deliberately rather than
    incidentally.
    """
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        metadata = result.metadata
        title = metadata.get("title", "Unknown title")
        author = metadata.get("author", "Unknown author")
        year = metadata.get("year", "n.d.")
        genre = metadata.get("genre", "Unknown genre")
        description = metadata.get("description") or getattr(result, "document", "") or ""
        lines.append(f"[{index}] {title} by {author} ({year}, {genre}): {description}")
    return "\n".join(lines)


__all__ = [
    "RAG_MAX_TOKENS",
    "RAG_SYSTEM_PROMPT",
    "RAG_TEMPERATURE",
    "REFUSAL_MESSAGE",
    "format_context",
]

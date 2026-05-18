"""Pydantic request/response schemas for the search endpoints.

These models define the **wire format** of ``POST /search/books`` and
``POST /search/ask`` (routers land in Phase 7).  They are intentionally
separate from the service-internal :class:`~app.services.rag.RAGAnswer`
and :class:`~app.services.rag.SourceCitation` dataclasses so the public
contract can evolve without dragging service-layer types along.

Length constraints mirror ``docs/API_REFERENCE.md``:

* ``query``    -- 3..500 characters
* ``question`` -- 5..1000 characters
* ``limit``    -- 1..50 (default 10)

Sources returned to the caller carry only ``title``, ``author``, and ``score``
(cosine *similarity*, never raw distance).  ``score`` is constrained to
[0, 1] because ``VectorStore.search`` converts distance to similarity at
its boundary -- see ``docs/ARCHITECTURE.md`` § *Distance vs Similarity*.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchBooksRequest(BaseModel):
    """Request payload for ``POST /search/books`` (semantic catalogue search)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(
        ..., min_length=3, max_length=500, description="Natural-language search phrase."
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of books to return.")


class BookHit(BaseModel):
    """A single ranked book returned by ``POST /search/books``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    author: str
    year: int
    genre: str
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity in [0, 1] (higher is more relevant)."
    )


class SearchBooksResponse(BaseModel):
    """Response payload for ``POST /search/books``."""

    model_config = ConfigDict(extra="forbid")

    query: str
    results: list[BookHit]


class AskRequest(BaseModel):
    """Request payload for ``POST /search/ask`` (RAG Q&A)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Natural-language question to answer from the catalogue.",
    )


class SourceBook(BaseModel):
    """Citation entry attached to a RAG answer.

    Deliberately minimal: only the fields a patron needs to find the book
    in the catalogue.  No ``id`` or ``description`` -- those belong on
    :class:`BookHit`, not on grounded citations.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity in [0, 1].")


class AskResponse(BaseModel):
    """Response payload for ``POST /search/ask``."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    sources: list[SourceBook]
    cached: bool


__all__ = [
    "AskRequest",
    "AskResponse",
    "BookHit",
    "SearchBooksRequest",
    "SearchBooksResponse",
    "SourceBook",
]

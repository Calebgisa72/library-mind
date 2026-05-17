"""ChromaDB-backed vector store for the book catalogue.

ChromaDB stores embeddings in an HNSW index with *cosine distance* in the
range [0, 2] (0 = identical, 2 = maximally dissimilar).  The public API of
LibraryMind uses *similarity* in the range [0, 1] (1 = identical, 0 = unrelated).

The conversion ``similarity = max(0.0, 1.0 - distance)`` is performed exactly
once — at the boundary of :meth:`VectorStore.search` — so no caller ever sees
a raw distance value.  See ``docs/ARCHITECTURE.md § Distance vs Similarity``
for the full rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb

from app.core.logging import get_logger
from app.core.settings import Settings

log = get_logger(__name__)

_COSINE_SPACE: dict[str, str] = {"hnsw:space": "cosine"}


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single result returned from :meth:`VectorStore.search`.

    Parameters
    ----------
    id:
        The book's identifier (matches ``Book.id`` in ``books.json``).
    score:
        Cosine *similarity* in ``[0, 1]``.  Higher is more relevant.
        This is **not** the raw distance returned by ChromaDB.
    metadata:
        Arbitrary metadata stored alongside the embedding at upsert time
        (e.g. title, author, genre, year).
    """

    id: str
    score: float
    metadata: dict[str, Any]


class VectorStore:
    """Thin, async-friendly wrapper around a ChromaDB persistent collection.

    Instantiate once at application startup (or in the seed script) and reuse
    across requests.  All heavy I/O happens in the ChromaDB client itself;
    the wrapper's own methods are lightweight and synchronous (ChromaDB's
    embedded client is synchronous under the hood).

    Parameters
    ----------
    settings:
        Application settings supplying ``chroma_persist_dir`` and
        ``chroma_collection_name``.
    """

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata=_COSINE_SPACE,
        )
        log.info(
            "vector_store.ready",
            persist_dir=settings.chroma_persist_dir,
            collection=settings.chroma_collection_name,
            count=self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert or update documents in the collection.

        Parameters
        ----------
        ids:
            Unique identifiers for each document (one per embedding).
        embeddings:
            Embedding vectors, one per document.
        documents:
            The raw text that was embedded (stored for reference).
        metadatas:
            Arbitrary key/value metadata stored alongside each vector.
            Values must be ``str | int | float | bool``.

        Raises ``chromadb.errors.ChromaError`` on failure (unexpected;
        wrapping is left to callers that need HTTP error translation).
        """
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )
        log.info("vector_store.upsert", count=len(ids))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        embedding: list[float],
        *,
        top_k: int,
    ) -> list[SearchResult]:
        """Return the *top_k* most similar documents.

        ChromaDB returns cosine *distance* (lower = more similar).  This
        method converts to *similarity* via ``max(0.0, 1.0 - distance)``
        **before** returning, so callers always work with similarity scores.

        Parameters
        ----------
        embedding:
            The query vector to compare against the stored embeddings.
        top_k:
            Maximum number of results to return.

        Returns
        -------
        list[SearchResult]
            Results sorted by similarity descending (most relevant first).
            May be shorter than *top_k* if the collection has fewer entries.
        """
        results = self._collection.query(
            query_embeddings=[embedding],  # type: ignore[arg-type]
            n_results=min(top_k, self._collection.count() or 1),
            include=["distances", "metadatas"],  # type: ignore[list-item]
        )

        ids: list[str] = results["ids"][0]
        distances: list[float] = results["distances"][0]  # type: ignore[index]
        metadatas: list[dict[str, Any]] = results["metadatas"][0]  # type: ignore[index, assignment]

        search_results: list[SearchResult] = []
        for book_id, distance, metadata in zip(ids, distances, metadatas, strict=False):
            similarity = max(0.0, 1.0 - distance)
            search_results.append(SearchResult(id=book_id, score=similarity, metadata=metadata))

        log.debug(
            "vector_store.search",
            top_k=top_k,
            returned=len(search_results),
        )
        return search_results

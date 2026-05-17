"""Seed the ChromaDB vector store from the books catalogue.

Usage::

    python -m scripts.seed_vector_store

The script:

1. Loads ``app/data/books.json``.
2. Builds a rich embedding text for each book:
   ``"{title} by {author}. {description}"``.
3. Calls :class:`~app.services.embedding.EmbeddingService` to embed all
   texts in a single batched API call (cache misses only on re-runs).
4. Upserts the embeddings into the ChromaDB collection via
   :class:`~app.infrastructure.vector_store.VectorStore`.
5. Prints a one-line summary and exits 0 on success, 1 on failure.

Run this once after initial setup and again whenever ``books.json`` changes.
Re-running is safe: ChromaDB upserts are idempotent, and embedding results
are cached in Redis so repeated runs cost nothing if the cache is warm.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.core.logging import get_logger
from app.core.settings import Settings
from app.infrastructure.cache import Cache
from app.infrastructure.vector_store import VectorStore
from app.providers.resilient import ResilientAIService
from app.services.embedding import EmbeddingService

log = get_logger(__name__)

_BOOKS_PATH = Path(__file__).parent.parent / "app" / "data" / "books.json"


def _build_embed_text(book: dict) -> str:  # type: ignore[type-arg]
    """Compose the text that will be embedded for a single book."""
    return f"{book['title']} by {book['author']}. {book['description']}"


async def _seed() -> None:
    settings = Settings()  # type: ignore[call-arg]

    with _BOOKS_PATH.open(encoding="utf-8") as fh:
        books: list[dict] = json.load(fh)  # type: ignore[type-arg]

    if not books:
        log.error("seed.no_books", path=str(_BOOKS_PATH))
        print("ERROR: books.json is empty.", file=sys.stderr)
        sys.exit(1)

    log.info("seed.start", count=len(books), path=str(_BOOKS_PATH))

    ai_service = ResilientAIService.from_settings(settings)
    cache = Cache(settings=settings)
    embedding_service = EmbeddingService(
        ai_service=ai_service,
        cache=cache,
        model=settings.openai_embedding_model,
    )
    vector_store = VectorStore(settings=settings)

    texts = [_build_embed_text(b) for b in books]
    ids = [b["id"] for b in books]
    metadatas = [
        {
            "title": b["title"],
            "author": b["author"],
            "year": b["year"],
            "genre": b["genre"],
        }
        for b in books
    ]

    log.info("seed.embedding", count=len(texts))
    embeddings = await embedding_service.embed_many(texts)

    vector_store.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    print(f"{len(books)} books ingested into collection '{settings.chroma_collection_name}'.")
    log.info("seed.done", count=len(books), collection=settings.chroma_collection_name)


def main() -> None:
    try:
        asyncio.run(_seed())
    except Exception as exc:
        log.exception("seed.error", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Routers for semantic search and RAG Q&A.

Endpoints
---------
POST /search/books
    Semantic catalogue search using cosine similarity.

POST /search/ask
    Retrieval-augmented Q&A grounded in the book catalogue.

Both endpoints delegate all business logic to the service layer; the routers
only validate input (via Pydantic schemas) and shape the JSON output.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_embedding_service, get_rag_service, get_vector_store
from app.infrastructure.vector_store import VectorStore
from app.schemas.errors import ErrorResponse
from app.schemas.search import (
    AskRequest,
    AskResponse,
    BookHit,
    SearchBooksRequest,
    SearchBooksResponse,
    SourceBook,
)
from app.services.embedding import EmbeddingService
from app.services.rag import RAGService

router = APIRouter(tags=["Search"])


@router.post(
    "/search/books",
    response_model=SearchBooksResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "AI provider unavailable"},
    },
    summary="Semantic catalogue search",
    description=(
        "Search the library catalogue by meaning rather than exact keywords. "
        "Returns the top matching books ranked by cosine similarity."
    ),
)
async def search_books(
    body: SearchBooksRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> SearchBooksResponse:
    """Embed the query and return the top-K most similar catalogue books."""
    vector = await embedding_service.embed_one(body.query)
    results = vector_store.search(vector, top_k=body.limit)
    hits = [
        BookHit(
            id=r.id,
            title=str(r.metadata.get("title", "")),
            author=str(r.metadata.get("author", "")),
            year=int(r.metadata.get("year", 0)),
            genre=str(r.metadata.get("genre", "")),
            score=r.score,
        )
        for r in results
    ]
    return SearchBooksResponse(query=body.query, results=hits)


@router.post(
    "/search/ask",
    response_model=AskResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "AI provider unavailable"},
    },
    summary="RAG-powered Q&A",
    description=(
        "Answer a patron's question using only the library catalogue as context. "
        "Returns the answer text, source book citations, and a cache flag."
    ),
)
async def ask(
    body: AskRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> AskResponse:
    """Run the RAG pipeline and return a grounded answer with source citations."""
    result = await rag_service.answer(body.question)
    sources = [SourceBook(title=s.title, author=s.author, score=s.score) for s in result.sources]
    return AskResponse(answer=result.answer, sources=sources, cached=result.cached)

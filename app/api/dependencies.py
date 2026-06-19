"""FastAPI dependency injection seams.

Each factory is decorated with ``@lru_cache(maxsize=1)`` so exactly one
instance is shared across the entire process lifetime.  This matches the
"singleton" pattern expected for stateful collaborators like the Redis
connection, ChromaDB client, and conversation store.

Routers depend on these functions via ``Depends()``.  Tests can override
them using ``app.dependency_overrides``.

Construction order matters:
    Settings -> (ai_service, cache, vector_store, usage_tracker, rate_limiter)
    -> embedding_service
    -> rag_service
    -> (chatbot_service, classifier_service, summariser_service)

All dependencies are zero-argument callables so ``lru_cache`` works
without a custom hash key.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.settings import get_settings
from app.infrastructure.cache import Cache
from app.infrastructure.rate_limiter import TokenBucketRateLimiter
from app.infrastructure.usage_tracker import UsageTracker
from app.infrastructure.vector_store import VectorStore
from app.providers.resilient import ResilientAIService
from app.services.chatbot import ChatbotService
from app.services.classifier import ClassifierService
from app.services.embedding import EmbeddingService
from app.services.rag import RAGService
from app.services.summariser import SummariserService


@lru_cache(maxsize=1)
def get_ai_service() -> ResilientAIService:
    """Return the process-wide resilient AI orchestrator.

    The usage tracker is injected here so the orchestrator records every
    successful AI call (generate / chat / embed) at a single chokepoint.
    """
    return ResilientAIService.from_settings(
        get_settings(),
        usage_tracker=get_usage_tracker(),
    )


@lru_cache(maxsize=1)
def get_cache() -> Cache:
    """Return the process-wide Redis cache (no-op when Redis is down)."""
    return Cache(settings=get_settings())


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Return the process-wide ChromaDB vector store."""
    return VectorStore(settings=get_settings())


@lru_cache(maxsize=1)
def get_usage_tracker() -> UsageTracker:
    """Return the process-wide in-memory usage tracker."""
    return UsageTracker()


@lru_cache(maxsize=1)
def get_rate_limiter() -> TokenBucketRateLimiter:
    """Return the process-wide token-bucket rate limiter."""
    settings = get_settings()
    return TokenBucketRateLimiter(
        requests_per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
    )


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Return the process-wide embedding service (with embedding cache)."""
    settings = get_settings()
    return EmbeddingService(
        ai_service=get_ai_service(),
        cache=get_cache(),
        model=settings.active_embedding_model,
    )


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    """Return the process-wide RAG service."""
    return RAGService(
        settings=get_settings(),
        ai_service=get_ai_service(),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
        cache=get_cache(),
        rate_limiter=get_rate_limiter(),
        usage_tracker=get_usage_tracker(),
    )


@lru_cache(maxsize=1)
def get_chatbot_service() -> ChatbotService:
    """Return the process-wide chatbot service."""
    return ChatbotService(
        settings=get_settings(),
        ai_service=get_ai_service(),
        rag_service=get_rag_service(),
    )


@lru_cache(maxsize=1)
def get_classifier_service() -> ClassifierService:
    """Return the process-wide ticket classifier service."""
    return ClassifierService(ai_service=get_ai_service())


@lru_cache(maxsize=1)
def get_summariser_service() -> SummariserService:
    """Return the process-wide review summariser service."""
    return SummariserService(ai_service=get_ai_service())


__all__ = [
    "get_ai_service",
    "get_cache",
    "get_chatbot_service",
    "get_classifier_service",
    "get_embedding_service",
    "get_rag_service",
    "get_rate_limiter",
    "get_summariser_service",
    "get_usage_tracker",
    "get_vector_store",
]

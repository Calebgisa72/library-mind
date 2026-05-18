"""Service layer — business logic.

Each service is a thin orchestrator that composes the AI provider layer
with the infrastructure layer (cache, rate limiter, usage tracker) to
fulfil a single use case.

Phase 3 public surface:

* :class:`~app.services.embedding.EmbeddingService` — generate & cache embeddings.

Phase 4 public surface:

* :class:`~app.services.rag.RAGService` — retrieval-augmented Q&A pipeline.
* :class:`~app.services.rag.RAGAnswer` — immutable answer dataclass.
* :class:`~app.services.rag.SourceCitation` — single source citation.

Planned services:

* :mod:`app.services.chatbot` — multi-turn conversational agent (Part 5).
* :mod:`app.services.classifier` — support-ticket classification (Part 6).
* :mod:`app.services.summariser` — book-review summarisation (Part 6).

Each service is constructed via the dependency container (defined later)
to keep them testable and free of global state.
"""

from app.services.embedding import EmbeddingService
from app.services.rag import RAGAnswer, RAGService, SourceCitation

__all__ = ["EmbeddingService", "RAGAnswer", "RAGService", "SourceCitation"]

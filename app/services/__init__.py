"""Service layer - business logic.

Each service is a thin orchestrator that composes the AI provider layer
with the infrastructure layer (cache, rate limiter, usage tracker) to
fulfil a single use case.

Phase 3: EmbeddingService.
Phase 4: RAGService, RAGAnswer, SourceCitation.
Phase 5: ChatbotService, ChatReply, ConversationStore, Message.
Planned: classifier (Part 6), summariser (Part 6).

Each service is constructed via dependency injection to keep them
testable and free of global state.
"""

from app.services.chatbot import ChatbotService, ChatReply, ConversationStore, Message
from app.services.embedding import EmbeddingService
from app.services.rag import RAGAnswer, RAGService, SourceCitation

__all__ = [
    "ChatReply",
    "ChatbotService",
    "ConversationStore",
    "EmbeddingService",
    "Message",
    "RAGAnswer",
    "RAGService",
    "SourceCitation",
]

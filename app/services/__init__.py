"""Service layer - business logic.

Each service is a thin orchestrator that composes the AI provider layer
with the infrastructure layer (cache, rate limiter, usage tracker) to
fulfil a single use case.

Phase 3: EmbeddingService.
Phase 4: RAGService, RAGAnswer, SourceCitation.
Phase 5: ChatbotService, ChatReply, ConversationStore, Message.
Phase 6: ClassifierService, TicketClassification, SummariserService, ReviewSummary.

Each service is constructed via dependency injection to keep them
testable and free of global state.
"""

from app.services.chatbot import ChatbotService, ChatReply, ConversationStore, Message
from app.services.classifier import ClassifierService, TicketClassification
from app.services.embedding import EmbeddingService
from app.services.rag import RAGAnswer, RAGService, SourceCitation
from app.services.summariser import ReviewSummary, SummariserService

__all__ = [
    "ChatReply",
    "ChatbotService",
    "ClassifierService",
    "ConversationStore",
    "EmbeddingService",
    "Message",
    "RAGAnswer",
    "RAGService",
    "ReviewSummary",
    "SourceCitation",
    "SummariserService",
    "TicketClassification",
]

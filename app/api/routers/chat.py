"""Router for the multi-turn AI librarian chatbot.

Endpoint
--------
POST /chat
    Send a message to the AI librarian within a named conversation.
    The chatbot maintains history per ``conversation_id`` and retrieves
    catalogue context for every turn.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chatbot_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.errors import ErrorResponse
from app.schemas.search import SourceBook
from app.services.chatbot import ChatbotService

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "AI provider unavailable"},
    },
    summary="Multi-turn AI librarian chatbot",
    description=(
        "Have a multi-turn conversation with the AI librarian. "
        "History is preserved per ``conversation_id``; different IDs are fully isolated."
    ),
)
async def chat(
    body: ChatRequest,
    chatbot: ChatbotService = Depends(get_chatbot_service),
) -> ChatResponse:
    """Deliver the patron's message to the chatbot and return its reply."""
    result = await chatbot.reply(body.conversation_id, body.message)
    sources = [SourceBook(title=s.title, author=s.author, score=s.score) for s in result.sources]
    return ChatResponse(
        conversation_id=body.conversation_id,
        reply=result.reply,
        sources=sources,
    )

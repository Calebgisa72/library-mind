"""AI librarian chatbot service with in-memory conversation memory.

:class:`ChatbotService` implements the multi-turn conversational endpoint.
The reply pipeline is::

    retrieve history (last N messages from ConversationStore)
        -> retrieve context (RAGService.retrieve_context — embedding + vector search)
        -> build full messages list (system + context + history + user turn)
        -> ResilientAIService.generate_chat(messages, temperature, max_tokens)
        -> append user message + assistant reply to ConversationStore
        -> return ChatReply(reply, sources)

Design decisions
----------------
* **No duplication of embedding / search logic.**  :class:`ChatbotService`
  delegates to :meth:`~app.services.rag.RAGService.retrieve_context` for
  retrieval.  It does *not* call the vector store or embedding service
  directly.

* **Conversation isolation.**  Each ``conversation_id`` maps to an
  independent ``list[Message]`` inside :class:`ConversationStore`.  No
  history ever bleeds between IDs.

* **Truncation before the AI call.**  Only the most recent
  ``settings.chat_history_max_messages`` turns are forwarded to the model.
  This keeps every request within the model's context window regardless of
  how long a conversation grows.

* **No rate-limiter in this service.**  The chatbot path is rate-limited by
  the router layer (Phase 7) in the same way as every other endpoint.
  Pulling the limiter into the service would duplicate the concern.

* **No usage tracker in this service.**  Usage tracking for the generation
  call is wired at the API layer (Phase 7) after the result is returned.
  For now, cost transparency is satisfied by the provider's own INFO log
  line (provider, model, prompt_tokens, completion_tokens).

Thread-safety note: :class:`ConversationStore` mutations are single-statement
``list.append`` calls, which are atomic under CPython's GIL for in-process
use.  This is explicitly documented in ``docs/ARCHITECTURE.md`` as a
deliberate lab-scope simplification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from app.core.logging import get_logger
from app.core.settings import Settings
from app.prompts.chatbot import CHATBOT_SYSTEM_PROMPT, CHATBOT_TEMPERATURE
from app.services.rag import RAGService, SourceCitation

if TYPE_CHECKING:
    from app.providers.resilient import ResilientAIService

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Message:
    """A single turn in a conversation.

    ``role`` mirrors the OpenAI chat-completion convention so
    :meth:`as_chat_message` can build the wire-format dict without any
    additional mapping.
    """

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime

    def as_chat_message(self) -> dict[str, str]:
        """Return an OpenAI-style role/content dict for prompt construction."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class ChatReply:
    """Result of :meth:`ChatbotService.reply`.

    ``sources`` mirrors :class:`~app.services.rag.SourceCitation` so the
    API layer (Phase 7) can shape the response without additional conversion.
    """

    reply: str
    sources: list[SourceCitation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Conversation store
# ---------------------------------------------------------------------------


class ConversationStore:
    """In-memory store for conversation histories.

    Each conversation is identified by a caller-supplied string ID.
    Histories grow unbounded in memory; callers use :meth:`recent` to
    retrieve only the most-recent slice before forwarding to the model.

    Thread-safety: single-statement ``list.append`` mutations are safe
    under the CPython GIL for the single-process lab deployment.  A
    distributed deployment would replace this with a Redis-backed store.
    """

    def __init__(self) -> None:
        self._convs: dict[str, list[Message]] = {}

    def history(self, cid: str) -> list[Message]:
        """Return the full message history for conversation *cid*."""
        return list(self._convs.get(cid, []))

    def append(self, cid: str, message: Message) -> None:
        """Append *message* to the conversation identified by *cid*.

        Creates the conversation if it does not yet exist.
        """
        if cid not in self._convs:
            self._convs[cid] = []
        self._convs[cid].append(message)

    def recent(self, cid: str, n: int) -> list[Message]:
        """Return the *n* most recent messages for conversation *cid*.

        Returns all messages if the history has fewer than *n* turns.
        Returns an empty list if the conversation does not exist.
        """
        messages = self._convs.get(cid, [])
        return messages[-n:] if len(messages) > n else list(messages)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ChatbotService:
    """Multi-turn AI librarian grounded in the book catalogue.

    Parameters
    ----------
    settings:
        Application settings (``chat_history_max_messages``,
        ``chat_max_tokens``).
    ai_service:
        Resilient multi-provider AI orchestrator.  Called via
        ``generate_chat`` which accepts the full conversation history.
    rag_service:
        RAG pipeline used for retrieval only (``retrieve_context``).
        The chatbot does not duplicate embedding or vector-search logic.
    store:
        In-memory conversation store.  Injected for testability; defaults
        to a new :class:`ConversationStore` when ``None``.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        ai_service: ResilientAIService,
        rag_service: RAGService,
        store: ConversationStore | None = None,
    ) -> None:
        self._settings = settings
        self._ai = ai_service
        self._rag = rag_service
        self._store = store if store is not None else ConversationStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def reply(self, conversation_id: str, message: str) -> ChatReply:
        """Generate the next librarian reply for *conversation_id*.

        Parameters
        ----------
        conversation_id:
            Caller-supplied identifier.  Different IDs are completely
            isolated; history never bleeds between conversations.
        message:
            The patron's latest message.

        Returns
        -------
        ChatReply
            The assistant's reply text plus the catalogue sources used to
            ground it.  ``sources`` is empty when no catalogue match was
            found or when the patron sent a greeting with no retrieval need.

        Raises
        ------
        AllProvidersFailedError
            When every configured AI provider fails to generate.
        """
        # Retrieve the truncated conversation history so the model has context
        # from prior turns without exceeding its context-window budget.
        history = self._store.recent(conversation_id, self._settings.chat_history_max_messages)

        # Ground the reply in the catalogue — this is an embedding + search
        # call that returns (sources, context_block) without an AI generation.
        sources, context_block = await self._rag.retrieve_context(message)

        # Compose the full messages list:
        # [system + catalogue context] + [conversation history] + [user turn]
        system_content = CHATBOT_SYSTEM_PROMPT
        if context_block:
            system_content = f"{CHATBOT_SYSTEM_PROMPT}\n\nCATALOGUE CONTEXT:\n{context_block}"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content},
            *[m.as_chat_message() for m in history],
            {"role": "user", "content": message},
        ]

        log.info(
            "chatbot.reply",
            conversation_id=conversation_id,
            n_history=len(history),
            n_sources=len(sources),
        )

        result = await self._ai.generate_chat(
            messages,
            temperature=CHATBOT_TEMPERATURE,
            max_tokens=self._settings.chat_max_tokens,
        )

        now = datetime.now(tz=UTC)
        self._store.append(
            conversation_id,
            Message(role="user", content=message, timestamp=now),
        )
        self._store.append(
            conversation_id,
            Message(role="assistant", content=result.text, timestamp=now),
        )

        return ChatReply(reply=result.text, sources=sources)


__all__ = ["ChatReply", "ChatbotService", "ConversationStore", "Message"]

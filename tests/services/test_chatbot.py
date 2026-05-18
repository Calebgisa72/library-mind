"""Tests for app.services.chatbot.ChatbotService.

Covers every Phase 5 acceptance criterion:

* "Starting a new conversation with 'Hi!' produces a friendly greeting"
* "Asking 'Recommend a science fiction book' returns a grounded recommendation"
* "Following up with 'Tell me more about that one' produces a detailed answer
  about the previously recommended book (proving memory works)"
* "Different conversation IDs maintain separate histories"

And the spec-required unit tests:

* test_friendly_greeting_for_hi
* test_grounded_recommendation_for_scifi_request
* test_memory_across_turns
* test_separate_conversation_ids_isolated
* test_truncates_history_to_max_messages
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chatbot import (
    ChatbotService,
    ChatReply,
    ConversationStore,
    Message,
)
from app.services.rag import SourceCitation

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeSettings:
    chat_history_max_messages: int = 10
    chat_max_tokens: int = 512


def _make_source(
    title: str = "Dune", author: str = "Frank Herbert", score: float = 0.85
) -> SourceCitation:
    return SourceCitation(title=title, author=author, score=score)


def _make_generation_result(text: str = "Here is my recommendation.") -> MagicMock:
    result = MagicMock()
    result.text = text
    result.provider = "openai"
    result.model = "gpt-4o-mini"
    result.prompt_tokens = 80
    result.completion_tokens = 40
    return result


def _make_ai_service(text: str = "Here is my recommendation.") -> MagicMock:
    svc = MagicMock()
    svc.model = "gpt-4o-mini"
    svc.generate_chat = AsyncMock(return_value=_make_generation_result(text))
    return svc


def _make_rag_service(
    sources: list[SourceCitation] | None = None,
    context_block: str = "",
) -> MagicMock:
    """Fake RAGService that returns a fixed (sources, context_block) pair."""
    svc = MagicMock()
    svc.retrieve_context = AsyncMock(return_value=(sources or [], context_block))
    return svc


def _make_service(
    *,
    settings: _FakeSettings | None = None,
    ai_service: MagicMock | None = None,
    rag_service: MagicMock | None = None,
    store: ConversationStore | None = None,
) -> tuple[ChatbotService, dict[str, MagicMock]]:
    ai = ai_service or _make_ai_service()
    rag = rag_service or _make_rag_service()
    svc_store = store if store is not None else ConversationStore()

    service = ChatbotService(
        settings=settings or _FakeSettings(),  # type: ignore[arg-type]
        ai_service=ai,
        rag_service=rag,
        store=svc_store,
    )
    return service, {"ai_service": ai, "rag_service": rag, "store": svc_store}


# ---------------------------------------------------------------------------
# ConversationStore unit tests
# ---------------------------------------------------------------------------


class TestConversationStore:
    def test_new_store_has_empty_history(self) -> None:
        store = ConversationStore()
        assert store.history("nonexistent") == []

    def test_append_creates_conversation(self) -> None:
        store = ConversationStore()
        msg = Message(role="user", content="Hi", timestamp=datetime.now(tz=UTC))
        store.append("c1", msg)
        assert store.history("c1") == [msg]

    def test_recent_returns_last_n(self) -> None:
        store = ConversationStore()
        msgs = [
            Message(role="user", content=str(i), timestamp=datetime.now(tz=UTC)) for i in range(5)
        ]
        for m in msgs:
            store.append("c1", m)
        recent = store.recent("c1", 3)
        assert len(recent) == 3
        assert recent == msgs[-3:]

    def test_recent_returns_all_when_fewer_than_n(self) -> None:
        store = ConversationStore()
        msg = Message(role="assistant", content="Hello", timestamp=datetime.now(tz=UTC))
        store.append("c1", msg)
        assert store.recent("c1", 10) == [msg]

    def test_conversations_are_isolated(self) -> None:
        store = ConversationStore()
        m1 = Message(role="user", content="conv1", timestamp=datetime.now(tz=UTC))
        m2 = Message(role="user", content="conv2", timestamp=datetime.now(tz=UTC))
        store.append("c1", m1)
        store.append("c2", m2)
        assert store.history("c1") == [m1]
        assert store.history("c2") == [m2]


# ---------------------------------------------------------------------------
# ChatbotService tests
# ---------------------------------------------------------------------------


class TestGreeting:
    @pytest.mark.anyio
    async def test_friendly_greeting_for_hi(self) -> None:
        """'Hi!' produces a non-empty friendly reply.

        Acceptance criterion: "Starting a new conversation with 'Hi!'
        produces a friendly greeting."
        """
        ai = _make_ai_service(text="Hello! Welcome to the library. How can I help you today?")
        service, _ = _make_service(ai_service=ai)

        result = await service.reply("conv-1", "Hi!")

        assert isinstance(result, ChatReply)
        assert len(result.reply) > 0
        assert "hello" in result.reply.lower() or "welcome" in result.reply.lower()

    @pytest.mark.anyio
    async def test_reply_returns_chat_reply_dataclass(self) -> None:
        service, _ = _make_service()
        result = await service.reply("conv-x", "Hello")
        assert isinstance(result, ChatReply)
        assert isinstance(result.reply, str)
        assert isinstance(result.sources, list)


class TestGroundedRecommendation:
    @pytest.mark.anyio
    async def test_grounded_recommendation_for_scifi_request(self) -> None:
        """RAG context is forwarded so the reply can cite a real catalogue title.

        Acceptance criterion: "Asking 'Recommend a science fiction book'
        returns a grounded recommendation."
        """
        dune = _make_source(title="Dune", author="Frank Herbert")
        rag = _make_rag_service(
            sources=[dune],
            context_block="[1] Dune by Frank Herbert (1965, Science Fiction): ...",
        )
        ai = _make_ai_service(
            text="I recommend *Dune* by Frank Herbert — a classic of science fiction."
        )
        service, _ = _make_service(ai_service=ai, rag_service=rag)

        result = await service.reply("conv-2", "Recommend a science fiction book")

        assert "Dune" in result.reply
        assert len(result.sources) == 1
        assert result.sources[0].title == "Dune"

    @pytest.mark.anyio
    async def test_sources_forwarded_from_rag(self) -> None:
        """Sources returned by retrieve_context are propagated to ChatReply."""
        sources = [
            _make_source(title="Foundation", author="Isaac Asimov"),
            _make_source(title="Dune", author="Frank Herbert"),
        ]
        rag = _make_rag_service(sources=sources, context_block="some context")
        service, _ = _make_service(rag_service=rag)

        result = await service.reply("conv-3", "Best sci-fi?")

        assert len(result.sources) == 2
        titles = {s.title for s in result.sources}
        assert titles == {"Foundation", "Dune"}

    @pytest.mark.anyio
    async def test_no_sources_when_catalogue_has_no_match(self) -> None:
        """Empty retrieval produces an empty sources list in the reply."""
        rag = _make_rag_service(sources=[], context_block="")
        service, _ = _make_service(rag_service=rag)

        result = await service.reply("conv-4", "What is the meaning of life?")

        assert result.sources == []


class TestMemory:
    @pytest.mark.anyio
    async def test_memory_across_turns(self) -> None:
        """Second turn can reference context from the first turn.

        Acceptance criterion: "Following up with 'Tell me more about that one'
        produces a detailed answer about the previously recommended book
        (proving memory works)."
        """
        dune = _make_source(title="Dune")
        rag = _make_rag_service(sources=[dune], context_block="[1] Dune ...")
        ai = _make_ai_service()
        store = ConversationStore()
        service, _ = _make_service(ai_service=ai, rag_service=rag, store=store)

        # Turn 1: recommend a thriller
        await service.reply("conv-mem", "Recommend a science fiction book")

        # After turn 1 the store should have user + assistant messages.
        history = store.history("conv-mem")
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

        # Turn 2: follow-up
        await service.reply("conv-mem", "Tell me more about that one")

        # The AI was called twice, and the second call received the history
        # from the first turn in the messages list.
        assert ai.generate_chat.await_count == 2
        second_call_messages = ai.generate_chat.call_args_list[1][0][0]

        # system message + 2 history turns + new user message = 4
        assert len(second_call_messages) == 4
        roles = [m["role"] for m in second_call_messages]
        assert roles == ["system", "user", "assistant", "user"]

    @pytest.mark.anyio
    async def test_history_appended_after_each_turn(self) -> None:
        """User and assistant messages are stored after every reply."""
        store = ConversationStore()
        service, _ = _make_service(store=store)

        await service.reply("c1", "First message")
        await service.reply("c1", "Second message")

        history = store.history("c1")
        assert len(history) == 4  # 2 turns x (user + assistant)
        assert history[0].content == "First message"
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[2].content == "Second message"
        assert history[3].role == "assistant"


class TestConversationIsolation:
    @pytest.mark.anyio
    async def test_separate_conversation_ids_isolated(self) -> None:
        """Messages from different conversation IDs never mix.

        Acceptance criterion: "Different conversation IDs maintain separate
        histories."
        """
        store = ConversationStore()
        ai = _make_ai_service()
        service, _ = _make_service(ai_service=ai, store=store)

        await service.reply("conv-A", "Hello from A")
        await service.reply("conv-B", "Hello from B")
        await service.reply("conv-A", "Second from A")

        history_a = store.history("conv-A")
        history_b = store.history("conv-B")

        # conv-A has two turns (2 x user+assistant = 4 messages)
        assert len(history_a) == 4
        # conv-B has one turn (1 x user+assistant = 2 messages)
        assert len(history_b) == 2

        # No conv-B content in conv-A history
        a_contents = {m.content for m in history_a}
        assert "Hello from B" not in a_contents

    @pytest.mark.anyio
    async def test_second_call_includes_only_own_history(self) -> None:
        """The messages forwarded to the AI contain history from one conv only."""
        store = ConversationStore()
        ai = _make_ai_service()
        service, _ = _make_service(ai_service=ai, store=store)

        # Populate conv-A first
        await service.reply("conv-A", "Message from A")
        # Now call conv-B
        await service.reply("conv-B", "Message from B")

        # Second call args: messages for conv-B
        second_call_msgs = ai.generate_chat.call_args_list[1][0][0]
        contents = [m["content"] for m in second_call_msgs]
        # conv-A message must not appear
        assert not any("Message from A" in c for c in contents)


class TestHistoryTruncation:
    @pytest.mark.anyio
    async def test_truncates_history_to_max_messages(self) -> None:
        """Only the last N messages are forwarded to the AI.

        Acceptance criterion: "Conversation history must be truncated to stay
        within the model's context window (keep only the most recent N
        messages)."
        """
        settings = _FakeSettings(chat_history_max_messages=4)
        ai = _make_ai_service()
        store = ConversationStore()

        # Pre-populate with 10 messages (5 user/assistant pairs)
        _ts = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(10):
            role: str = "user" if i % 2 == 0 else "assistant"
            store.append("c1", Message(role=role, content=f"msg-{i}", timestamp=_ts))  # type: ignore[arg-type]

        service = ChatbotService(
            settings=settings,  # type: ignore[arg-type]
            ai_service=ai,
            rag_service=_make_rag_service(),
            store=store,
        )
        await service.reply("c1", "New message")

        call_messages = ai.generate_chat.call_args_list[0][0][0]
        # 1 system + 4 history + 1 new user = 6
        assert len(call_messages) == 6

    @pytest.mark.anyio
    async def test_history_not_truncated_when_within_limit(self) -> None:
        """When history is within the limit, all messages are forwarded."""
        settings = _FakeSettings(chat_history_max_messages=10)
        ai = _make_ai_service()
        store = ConversationStore()
        _ts = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(4):
            role = "user" if i % 2 == 0 else "assistant"
            store.append("c1", Message(role=role, content=f"msg-{i}", timestamp=_ts))  # type: ignore[arg-type]

        service = ChatbotService(
            settings=settings,  # type: ignore[arg-type]
            ai_service=ai,
            rag_service=_make_rag_service(),
            store=store,
        )
        await service.reply("c1", "New")

        call_messages = ai.generate_chat.call_args_list[0][0][0]
        # 1 system + 4 history + 1 user = 6
        assert len(call_messages) == 6


class TestPromptComposition:
    @pytest.mark.anyio
    async def test_system_prompt_is_first_message(self) -> None:
        """The system message with the librarian persona must come first."""
        from app.prompts.chatbot import CHATBOT_SYSTEM_PROMPT

        ai = _make_ai_service()
        service, _ = _make_service(ai_service=ai)

        await service.reply("c1", "Hello")

        messages = ai.generate_chat.call_args_list[0][0][0]
        assert messages[0]["role"] == "system"
        assert CHATBOT_SYSTEM_PROMPT in messages[0]["content"]

    @pytest.mark.anyio
    async def test_context_block_injected_when_sources_found(self) -> None:
        """When RAG retrieves results the context block appears in the system message."""
        context = "[1] Dune by Frank Herbert: Great sci-fi."
        rag = _make_rag_service(
            sources=[_make_source()],
            context_block=context,
        )
        ai = _make_ai_service()
        service, _ = _make_service(ai_service=ai, rag_service=rag)

        await service.reply("c1", "Recommend sci-fi")

        messages = ai.generate_chat.call_args_list[0][0][0]
        assert context in messages[0]["content"]

    @pytest.mark.anyio
    async def test_no_context_block_when_no_sources(self) -> None:
        """When retrieval is empty, the system message contains no injected context block.

        The base CHATBOT_SYSTEM_PROMPT itself mentions 'CATALOGUE CONTEXT' in its
        rules text, so we check that no *appended* block (marked by the '\n\nCATALOGUE
        CONTEXT:\n' separator the service injects) is present.
        """
        from app.prompts.chatbot import CHATBOT_SYSTEM_PROMPT

        rag = _make_rag_service(sources=[], context_block="")
        ai = _make_ai_service()
        service, _ = _make_service(ai_service=ai, rag_service=rag)

        await service.reply("c1", "What is 2+2?")

        messages = ai.generate_chat.call_args_list[0][0][0]
        system_content = messages[0]["content"]
        # No injected block: the system content must equal the bare prompt exactly.
        assert system_content == CHATBOT_SYSTEM_PROMPT
        # The service-injected separator must not be present.
        assert "\n\nCATALOGUE CONTEXT:\n" not in system_content

    @pytest.mark.anyio
    async def test_temperature_and_max_tokens_forwarded(self) -> None:
        """Generation parameters are forwarded from the service to the AI."""
        from app.prompts.chatbot import CHATBOT_TEMPERATURE

        settings = _FakeSettings(chat_max_tokens=256)
        ai = _make_ai_service()
        service = ChatbotService(
            settings=settings,  # type: ignore[arg-type]
            ai_service=ai,
            rag_service=_make_rag_service(),
        )

        await service.reply("c1", "Hello")

        kwargs = ai.generate_chat.call_args.kwargs
        assert kwargs["temperature"] == CHATBOT_TEMPERATURE
        assert kwargs["max_tokens"] == 256

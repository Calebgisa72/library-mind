"""Tests for POST /chat.

Roadmap testing requirements covered:
* test_chat_isolates_conversations — different conv IDs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_chatbot_service
from app.main import app
from app.services.chatbot import ChatReply
from app.services.rag import SourceCitation

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_chatbot(reply: str = "I recommend *Dune* by Frank Herbert.") -> MagicMock:
    svc = MagicMock()
    svc.reply = AsyncMock(
        return_value=ChatReply(
            reply=reply,
            sources=[SourceCitation(title="Dune", author="Frank Herbert", score=0.87)],
        )
    )
    return svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


class TestChat:
    def test_chat_returns_200_with_reply(self, client: TestClient) -> None:
        """Valid request returns 200 with reply, sources, and conversation_id."""
        app.dependency_overrides[get_chatbot_service] = lambda: _fake_chatbot()
        try:
            r = client.post(
                "/chat",
                json={"conversation_id": "sess-001", "message": "Recommend a sci-fi book."},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["conversation_id"] == "sess-001"
            assert "reply" in data
            assert "sources" in data
            assert len(data["sources"]) == 1
            assert data["sources"][0]["title"] == "Dune"
        finally:
            app.dependency_overrides.clear()

    def test_chat_isolates_conversations(self, client: TestClient) -> None:
        """Different conversation_id values route to separate conversations."""
        replies: dict[str, str] = {}

        async def _reply(conv_id: str, message: str) -> ChatReply:
            replies[conv_id] = message
            return ChatReply(reply=f"Reply for {conv_id}", sources=[])

        svc = MagicMock()
        svc.reply = _reply

        app.dependency_overrides[get_chatbot_service] = lambda: svc
        try:
            r1 = client.post("/chat", json={"conversation_id": "conv-A", "message": "Hello A"})
            r2 = client.post("/chat", json={"conversation_id": "conv-B", "message": "Hello B"})
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.json()["conversation_id"] == "conv-A"
            assert r2.json()["conversation_id"] == "conv-B"
            # Each conversation received its own message
            assert replies["conv-A"] == "Hello A"
            assert replies["conv-B"] == "Hello B"
        finally:
            app.dependency_overrides.clear()

    def test_chat_response_schema(self, client: TestClient) -> None:
        """Response has exactly conversation_id, reply, sources."""
        app.dependency_overrides[get_chatbot_service] = lambda: _fake_chatbot()
        try:
            r = client.post("/chat", json={"conversation_id": "s1", "message": "Hello"})
            assert r.status_code == 200
            assert {"conversation_id", "reply", "sources"} == set(r.json().keys())
        finally:
            app.dependency_overrides.clear()

    def test_chat_source_schema(self, client: TestClient) -> None:
        """Each source has exactly title, author, score."""
        app.dependency_overrides[get_chatbot_service] = lambda: _fake_chatbot()
        try:
            r = client.post("/chat", json={"conversation_id": "s1", "message": "Hello"})
            assert r.status_code == 200
            source = r.json()["sources"][0]
            assert {"title", "author", "score"} == set(source.keys())
        finally:
            app.dependency_overrides.clear()

    def test_chat_no_sources_returns_empty_list(self, client: TestClient) -> None:
        """A reply with no catalogue sources returns an empty sources list."""
        svc = MagicMock()
        svc.reply = AsyncMock(return_value=ChatReply(reply="Hello!", sources=[]))
        app.dependency_overrides[get_chatbot_service] = lambda: svc
        try:
            r = client.post("/chat", json={"conversation_id": "s2", "message": "Hi"})
            assert r.status_code == 200
            assert r.json()["sources"] == []
        finally:
            app.dependency_overrides.clear()

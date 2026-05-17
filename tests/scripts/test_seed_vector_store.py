"""Smoke tests for scripts.seed_vector_store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def books_json(tmp_path: Path) -> Path:
    """Write a minimal two-book catalogue to a temp file and return the path."""
    data = [
        {
            "id": "seed-001",
            "title": "Test Book One",
            "author": "Author A",
            "year": 2000,
            "genre": "Fiction",
            "description": "A test book about testing. It is used to verify seed behaviour. Nothing more.",
        },
        {
            "id": "seed-002",
            "title": "Test Book Two",
            "author": "Author B",
            "year": 2001,
            "genre": "Mystery",
            "description": "A second test book. Also for testing purposes. It has a different genre.",
        },
    ]
    p = tmp_path / "books.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings_mock(chroma_dir: str) -> MagicMock:
    s = MagicMock()
    s.chroma_persist_dir = chroma_dir
    s.chroma_collection_name = "books_test"
    s.openai_embedding_model = "text-embedding-3-small"
    s.cache_enabled = False
    s.redis_url = "redis://localhost:6379/0"
    s.cache_default_ttl_seconds = 3600
    return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSeedVectorStore:
    @pytest.mark.anyio
    async def test_seed_ingests_all_books(self, tmp_path: Path, books_json: Path) -> None:
        """The seed function should embed and upsert all books without error."""
        from scripts.seed_vector_store import _seed

        chroma_dir = str(tmp_path / "chroma")
        settings_mock = _make_settings_mock(chroma_dir)

        upserted_ids: list[str] = []

        fake_collection = MagicMock()
        fake_collection.count.return_value = 0

        def capture_upsert(**kwargs: object) -> None:
            upserted_ids.extend(kwargs["ids"])  # type: ignore[arg-type]

        fake_collection.upsert.side_effect = capture_upsert

        with (
            patch("scripts.seed_vector_store._BOOKS_PATH", books_json),
            patch("scripts.seed_vector_store.Settings", return_value=settings_mock),
            patch("scripts.seed_vector_store.ResilientAIService.from_settings") as mock_ai_factory,
            patch("chromadb.PersistentClient") as mock_chroma,
        ):
            mock_ai = MagicMock()
            # embed() returns one vector per text.
            mock_ai.embed = AsyncMock(
                side_effect=lambda texts: [
                    [0.1] * 3 for _ in (texts if isinstance(texts, list) else [texts])
                ]
            )
            mock_ai_factory.return_value = mock_ai

            mock_chroma.return_value.get_or_create_collection.return_value = fake_collection

            await _seed()

        assert set(upserted_ids) == {"seed-001", "seed-002"}

    def test_build_embed_text_format(self) -> None:
        """The text built for embedding must combine title, author, and description."""
        from scripts.seed_vector_store import _build_embed_text

        book = {
            "title": "Great Book",
            "author": "Jane Doe",
            "description": "A really great book about things.",
        }
        text = _build_embed_text(book)
        assert text == "Great Book by Jane Doe. A really great book about things."

    @pytest.mark.anyio
    async def test_seed_exits_on_empty_books(self, tmp_path: Path) -> None:
        """Passing an empty books.json must trigger sys.exit(1)."""

        empty_json = tmp_path / "empty.json"
        empty_json.write_text("[]", encoding="utf-8")

        from scripts.seed_vector_store import _seed

        settings_mock = _make_settings_mock(str(tmp_path / "chroma"))

        with (
            patch("scripts.seed_vector_store._BOOKS_PATH", empty_json),
            patch("scripts.seed_vector_store.Settings", return_value=settings_mock),
            pytest.raises(SystemExit) as exc_info,
        ):
            await _seed()

        assert exc_info.value.code == 1

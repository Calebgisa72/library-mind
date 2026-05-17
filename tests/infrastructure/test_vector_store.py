"""Tests for app.infrastructure.vector_store.VectorStore."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.vector_store import SearchResult, VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(
    persist_dir: str = "./data/chroma_test",
    collection_name: str = "books_test",
) -> MagicMock:
    s = MagicMock()
    s.chroma_persist_dir = persist_dir
    s.chroma_collection_name = collection_name
    return s


def _unit_vector(dim: int, index: int) -> list[float]:
    """Return a unit vector of *dim* dimensions with a 1.0 at *index*."""
    v = [0.0] * dim
    v[index] = 1.0
    return v


# ---------------------------------------------------------------------------
# Integration tests using a real ChromaDB temp collection
# ---------------------------------------------------------------------------


class TestVectorStoreIntegration:
    """Use a real ChromaDB in-memory-equivalent via a tmp_path directory."""

    @pytest.fixture
    def store(self, tmp_path: Any) -> VectorStore:
        settings = _make_settings(persist_dir=str(tmp_path / "chroma"))
        return VectorStore(settings=settings)

    def test_upsert_then_search_returns_matches(self, store: VectorStore) -> None:
        """Seeded vectors should be retrievable and sorted by score descending."""
        dim = 4
        store.upsert(
            ids=["a", "b", "c"],
            embeddings=[
                _unit_vector(dim, 0),  # e0 = [1,0,0,0]
                _unit_vector(dim, 1),  # e1 = [0,1,0,0]
                _unit_vector(dim, 2),  # e2 = [0,0,1,0]
            ],
            documents=["doc a", "doc b", "doc c"],
            metadatas=[
                {"title": "Book A", "genre": "Fiction"},
                {"title": "Book B", "genre": "Mystery"},
                {"title": "Book C", "genre": "Fantasy"},
            ],
        )

        # Query with a vector identical to e0 — Book A should rank first.
        results = store.search(_unit_vector(dim, 0), top_k=3)

        assert len(results) == 3
        assert results[0].id == "a"
        # Scores must be descending.
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_returns_search_result_instances(self, store: VectorStore) -> None:
        store.upsert(
            ids=["x"],
            embeddings=[[1.0, 0.0]],
            documents=["doc x"],
            metadatas=[{"title": "X"}],
        )
        results = store.search([1.0, 0.0], top_k=1)
        assert isinstance(results[0], SearchResult)
        assert isinstance(results[0].score, float)
        assert isinstance(results[0].metadata, dict)

    def test_search_respects_top_k(self, store: VectorStore) -> None:
        dim = 8
        store.upsert(
            ids=[f"book-{i}" for i in range(5)],
            embeddings=[_unit_vector(dim, i) for i in range(5)],
            documents=[f"doc {i}" for i in range(5)],
            metadatas=[{"title": f"Book {i}"} for i in range(5)],
        )
        results = store.search(_unit_vector(dim, 0), top_k=2)
        assert len(results) <= 2

    def test_upsert_is_idempotent(self, store: VectorStore) -> None:
        """Upserting the same id twice should not raise or duplicate."""
        store.upsert(
            ids=["dup"],
            embeddings=[[1.0, 0.0]],
            documents=["first"],
            metadatas=[{"title": "Original"}],
        )
        store.upsert(
            ids=["dup"],
            embeddings=[[0.0, 1.0]],
            documents=["second"],
            metadatas=[{"title": "Updated"}],
        )
        results = store.search([0.0, 1.0], top_k=1)
        assert results[0].id == "dup"


# ---------------------------------------------------------------------------
# Unit test: distance → similarity conversion
# ---------------------------------------------------------------------------


class TestDistanceToSimilarityConversion:
    """Verify the exact conversion at the VectorStore.search boundary."""

    def test_search_converts_distance_to_similarity(self, tmp_path: Any) -> None:
        """ChromaDB returns distance; VectorStore must return 1 - distance."""
        settings = _make_settings(persist_dir=str(tmp_path / "chroma"))

        # Patch the chromadb PersistentClient so we control what query returns.
        fake_collection = MagicMock()
        fake_collection.count.return_value = 2
        fake_collection.query.return_value = {
            "ids": [["book-1", "book-2"]],
            "distances": [[0.2, 0.7]],
            "metadatas": [[{"title": "A"}, {"title": "B"}]],
        }

        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = fake_collection
            store = VectorStore(settings=settings)

        results = store.search([1.0, 0.0], top_k=2)

        assert len(results) == 2
        # distance 0.2 → similarity 0.8
        assert math.isclose(results[0].score, 0.8, rel_tol=1e-6)
        # distance 0.7 → similarity 0.3
        assert math.isclose(results[1].score, 0.3, rel_tol=1e-6)

    def test_search_clamps_similarity_to_zero_for_large_distances(self, tmp_path: Any) -> None:
        """Distances > 1.0 (possible in cosine space) must not produce negative scores."""
        settings = _make_settings(persist_dir=str(tmp_path / "chroma"))

        fake_collection = MagicMock()
        fake_collection.count.return_value = 1
        fake_collection.query.return_value = {
            "ids": [["book-far"]],
            "distances": [[1.5]],
            "metadatas": [[{"title": "Far"}]],
        }

        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.return_value.get_or_create_collection.return_value = fake_collection
            store = VectorStore(settings=settings)

        results = store.search([1.0], top_k=1)
        assert results[0].score == 0.0

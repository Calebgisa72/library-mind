"""Tests for app.infrastructure.keys."""

from __future__ import annotations

from app.infrastructure.keys import make_key


class TestMakeKey:
    def test_same_inputs_produce_same_key(self) -> None:
        """Determinism: identical arguments must always return the same key."""
        k1 = make_key("rag", "gpt-4o-mini", "abc123")
        k2 = make_key("rag", "gpt-4o-mini", "abc123")
        assert k1 == k2

    def test_different_parts_produce_different_keys(self) -> None:
        k1 = make_key("rag", "gpt-4o-mini", "question-A")
        k2 = make_key("rag", "gpt-4o-mini", "question-B")
        assert k1 != k2

    def test_different_scopes_produce_different_keys(self) -> None:
        k1 = make_key("rag", "model", "text")
        k2 = make_key("embedding", "model", "text")
        assert k1 != k2

    def test_key_format_version_scope_hash(self) -> None:
        """Key must have exactly three colon-separated segments."""
        key = make_key("rag", "some-part")
        parts = key.split(":")
        assert len(parts) == 3
        version, scope, digest = parts
        assert version == "v1"
        assert scope == "rag"
        assert len(digest) == 64  # sha256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in digest)

    def test_custom_version_prefix(self) -> None:
        k_v1 = make_key("rag", "x", version="v1")
        k_v2 = make_key("rag", "x", version="v2")
        assert k_v1.startswith("v1:rag:")
        assert k_v2.startswith("v2:rag:")
        # Different versions -> different keys even with same parts
        assert k_v1 != k_v2

    def test_no_parts_is_valid(self) -> None:
        """make_key with only a scope and no extra parts should not raise."""
        key = make_key("health")
        assert key.startswith("v1:health:")

    def test_non_string_parts_serialised_deterministically(self) -> None:
        """Integer and float parts must hash consistently."""
        k1 = make_key("embed", "model", 42, 3.14)
        k2 = make_key("embed", "model", 42, 3.14)
        assert k1 == k2

    def test_order_of_parts_matters(self) -> None:
        """Swapping part order must produce a different key."""
        k1 = make_key("scope", "a", "b")
        k2 = make_key("scope", "b", "a")
        assert k1 != k2

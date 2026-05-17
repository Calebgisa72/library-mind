"""Deterministic cache-key helpers.

Every cache key in LibraryMind has the same three-part format::

    {version}:{scope}:{sha256_of_parts}

* **version** -- a short prefix (``v1``, ``v2``, ...) that can be bumped
  whenever a prompt template or data shape changes, invalidating just that
  scope without flushing the entire Redis namespace.
* **scope** -- a human-readable namespace (``"rag"``, ``"embedding"``,
  ``"classify"``, etc.) that makes log output self-describing.
* **sha256_of_parts** -- a deterministic hex digest of the remaining
  arguments serialised as compact JSON, ensuring that identical inputs
  always map to the same key and different inputs never collide.

Usage::

    from app.infrastructure.keys import make_key

    key = make_key("rag", model, question)          # v1:rag:<hex>
    key = make_key("embedding", model, text)         # v1:embedding:<hex>
    key = make_key("rag", model, q, version="v2")   # v2:rag:<hex>

Why JSON serialisation instead of str(parts)?
----------------------------------------------
``str()`` produces ambiguous representations (e.g. ``str([1, 2])`` and
``str("1, 2")`` differ, but two slightly different calls could coincidentally
produce the same concatenated string).  ``json.dumps`` with sorted keys and
no whitespace gives a canonical, unambiguous encoding.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_key(scope: str, *parts: Any, version: str = "v1") -> str:
    """Return a versioned, deterministic cache key.

    Parameters
    ----------
    scope:
        Human-readable namespace for the key (e.g. ``"rag"``,
        ``"embedding"``).  Appears literally in the key so log lines
        are self-describing.
    *parts:
        Any JSON-serialisable values that uniquely identify the cached
        item (model name, hashed question text, etc.).  All parts are
        serialised together and hashed; order matters.
    version:
        Cache-key version prefix.  Bump this string (e.g. ``"v2"``)
        whenever the cached value's format or meaning changes, so stale
        entries are automatically ignored without a full Redis flush.

    Returns
    -------
    str
        Key in the form ``"{version}:{scope}:{sha256_hex}"``.

    Examples
    --------
    >>> make_key("rag", "gpt-4o-mini", "some-question-hash")
    'v1:rag:...'
    >>> # Same inputs always produce the same key:
    >>> make_key("rag", "a", "b") == make_key("rag", "a", "b")
    True
    """
    payload = json.dumps(parts, default=str, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{version}:{scope}:{digest}"

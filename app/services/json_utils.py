"""Defensive JSON parser for AI-generated structured output.

AI models frequently wrap their JSON responses in markdown code fences even
when explicitly instructed not to.  This helper strips those fences before
parsing so callers can rely on a clean ``dict`` rather than defending against
``json.JSONDecodeError`` at every call site.

This is the non-optional helper called out in both M3's notes and the lab
brief under *"Known pitfalls — JSON parsing failures"*.  Every service that
expects structured JSON output from an AI provider must route the raw
response through :func:`parse_ai_json` before passing it to
``json.loads`` or Pydantic.

The function raises :class:`~app.core.exceptions.ProviderError` on parse
failure so the global exception handler maps the error to HTTP 503 and the
caller sees a clear diagnostic body containing both the raw response and the
cleaned intermediate string.
"""

from __future__ import annotations

import json
import re
from typing import cast

from app.core.exceptions import ProviderError

# Matches both ``` and ```json fences, including optional leading whitespace on
# the fence line (models occasionally indent the delimiter).  re.MULTILINE so
# ^ and $ match at line boundaries inside the response string.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def parse_ai_json(raw: str) -> dict[str, object]:
    """Strip markdown fences and parse *raw* as JSON.

    Accepts responses in any of these forms (all produced in the wild)::

        {"key": "value"}
        ```json
        {"key": "value"}
        ```
        ```
        {"key": "value"}
        ```

    Parameters
    ----------
    raw:
        The verbatim string returned by the AI provider.

    Returns
    -------
    dict[str, object]
        The parsed JSON payload.

    Raises
    ------
    ProviderError
        When the cleaned string is not valid JSON.  The exception's
        ``detail`` dict carries ``raw_response``, ``cleaned``, and
        ``json_error`` so a 503 response body is diagnostic.
    """
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        return cast(dict[str, object], json.loads(cleaned))
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "AI model returned non-JSON output",
            detail={
                "raw_response": raw,
                "cleaned": cleaned,
                "json_error": str(exc),
            },
        ) from exc


__all__ = ["parse_ai_json"]

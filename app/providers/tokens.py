"""Local token-counting fallback via tiktoken.

Providers that use an official SDK (OpenAI, Anthropic) report token usage on
every generation call, so :class:`~app.providers.base.GenerationResult` carries
real counts and the :class:`~app.infrastructure.usage_tracker.UsageTracker`
can price them.

The AmaliAI gateway, however, is a thin OpenAI-compatible HTTP proxy and does
not always echo a ``usage`` object. Without it, token counts would be ``None``
-> recorded as ``0`` -> cost ``$0.00``, even though a real (billable) call was
made. To keep cost tracking accurate and on par with the SDK providers, this
module counts tokens locally with ``tiktoken`` whenever a provider omits usage.

The counts are estimates: they cover message content (plus a small per-message
overhead that mirrors OpenAI's chat accounting) but cannot capture every
provider-side detail. They are close enough for budget tracking and are only
used as a fallback -- when the provider reports real usage, that is used as-is.
"""

from __future__ import annotations

import tiktoken

from app.core.logging import get_logger

log = get_logger(__name__)

# gpt-4o / gpt-4o-mini (AmaliAI's default upstream) use the o200k_base encoding.
# Used whenever tiktoken does not recognise the model name.
_DEFAULT_ENCODING = "o200k_base"

# OpenAI's chat format adds a few tokens of structural overhead per message and
# per reply. These constants mirror OpenAI's documented accounting closely
# enough for cost estimation.
_TOKENS_PER_MESSAGE = 3
_TOKENS_PER_REPLY = 3


def _encoding_for(model: str) -> "tiktoken.Encoding":
    """Return a tiktoken encoding for *model*, falling back to a sane default."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding(_DEFAULT_ENCODING)


def count_text_tokens(text: str, model: str) -> int:
    """Return the tiktoken token count for *text* under *model*.

    Never raises: if tiktoken is unavailable (e.g. the encoding files cannot be
    fetched in a restricted environment) it falls back to a coarse
    ~4-characters-per-token estimate so cost tracking still produces a non-zero,
    order-of-magnitude-correct value.
    """
    if not text:
        return 0
    try:
        return len(_encoding_for(model).encode(text))
    except Exception as exc:  # noqa: BLE001 - counting must never break a response
        log.warning("token_count.tiktoken_failed", model=model, error=str(exc))
        return max(1, len(text) // 4)


def count_messages_tokens(messages: list[dict[str, str]], model: str) -> int:
    """Return an estimated prompt-token count for an OpenAI-style *messages* list.

    Sums the token count of each message's ``content`` and adds the small
    structural overhead OpenAI bills per message and per reply, so the estimate
    tracks closely with what the provider would have reported.
    """
    total = sum(count_text_tokens(m.get("content", ""), model) for m in messages)
    total += _TOKENS_PER_MESSAGE * len(messages) + _TOKENS_PER_REPLY
    return total


__all__ = ["count_messages_tokens", "count_text_tokens"]

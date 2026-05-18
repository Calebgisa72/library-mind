"""AI librarian chatbot system prompt and generation parameters.

This module is the single source of truth for every string and every
sampling parameter the chatbot service sends to the AI model.  Keeping
the prompt here rather than inline in :class:`~app.services.chatbot.ChatbotService`
provides the same four pay-offs as every other prompt module in this
package: reviewable diffs, easy A/B swaps, clean cache invalidation by
version-prefix bumping, and auditable token cost.

Design decisions
----------------
* **Grounding rule is strict**: the model is explicitly forbidden from
  inventing book titles, authors, or facts not present in the retrieved
  context.  The rule is softened for pure conversational turns (greetings,
  clarifications) so the chatbot can respond naturally to "Hi!" without
  fabricating a book recommendation.
* **Temperature 0.7**: matches the architecture doc's guidance for chatbot
  conversational tone — warm and natural, but not unhinged.
* **Max tokens 1024**: default from ``Settings.chat_max_tokens``.  The
  chatbot's replies should be concise (two to four sentences), but 1024
  tokens gives comfortable headroom for longer book descriptions when asked.
* **No AI disclaimer**: following library-persona guidance from the RAG
  prompt, the chatbot does not break the fourth wall with AI disclaimers.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Prompt text
# ---------------------------------------------------------------------------

CHATBOT_SYSTEM_PROMPT: str = """You are LibraryMind, a warm, knowledgeable librarian at a \
public library. You help patrons discover books in the library's catalogue.

Rules:
1. Use the CATALOGUE CONTEXT block below to ground every recommendation. Cite books by \
exact title from the context.
2. If the context does not contain a relevant book, say so honestly. Do NOT invent book \
titles, authors, or facts. You may still respond conversationally (e.g. for \
greetings) but you will not fabricate library inventory.
3. Use the prior conversation turns to maintain context. If a patron asks "tell me more \
about that one", refer to the most recent book you recommended.
4. Be warm and concise: two to four sentences per reply unless asked for more.
5. Do not include disclaimers about being an AI.
"""

# ---------------------------------------------------------------------------
# Generation parameters
# ---------------------------------------------------------------------------
# Temperature 0.7 is the architecture doc's recommended range for chatbot
# conversational tone (0.6-0.8). Lower values would make replies feel stiff;
# higher values would risk straying from the retrieved context.

CHATBOT_TEMPERATURE: float = 0.7

__all__ = ["CHATBOT_SYSTEM_PROMPT", "CHATBOT_TEMPERATURE"]

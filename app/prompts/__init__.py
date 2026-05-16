"""Prompt templates — first-class, versioned, reviewable.

Prompts are application logic, not string constants. Treating them as
such — putting each one in its own module, naming them, version-tagging
them in commit messages — makes them reviewable in PRs, A/B-testable in
later phases, and refactor-safe.

This package is the *only* place where prompt text lives. Services
import named templates from here; they never construct system prompts
inline. The rule is: **if you find yourself writing a triple-quoted
string inside a service, stop and add it to this package instead.**

Planned modules (each lands with its phase):

* :mod:`app.prompts.rag` — RAG system prompt (Part 4).
  Instructs the model to ground answers in retrieved context, cite
  source books by title, and admit insufficient information rather
  than fabricate.
* :mod:`app.prompts.chatbot` — librarian persona system prompt (Part 5).
  Warm, helpful, knowledgeable tone; refuses to fabricate book titles
  or authors when retrieval finds nothing.
* :mod:`app.prompts.classifier` — ticket classification prompt
  (Part 6, Task A). Returns structured JSON; includes 2-3 few-shot
  examples per category to anchor the model's output.
* :mod:`app.prompts.summariser` — review-aggregation prompt
  (Part 6, Task B). Instructs holistic synthesis over a list of
  reviews rather than per-review summarisation.

Conventions:

* Every prompt is exported as a typed string constant (e.g.
  ``RAG_SYSTEM_PROMPT: str``) and a module-level docstring explains
  *why* the prompt is shaped the way it is.
* When iterating on a prompt during development, include a short
  version tag in the cache-key prefix (``v1:rag:...``) so old cached
  responses do not mask the change. See ``docs/ARCHITECTURE.md`` §
  Caching Strategy.
* Few-shot examples live alongside their prompt in the same module,
  as a typed list of ``(input, output)`` pairs.
"""

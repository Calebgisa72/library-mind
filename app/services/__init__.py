"""Service layer — business logic.

Each service is a thin orchestrator that composes the AI provider layer
with the infrastructure layer (cache, rate limiter, usage tracker) to
fulfil a single use case.

Planned services:

* :mod:`app.services.embedding` — generate & cache embeddings (Part 3).
* :mod:`app.services.rag` — retrieval-augmented Q&A pipeline (Part 4).
* :mod:`app.services.chatbot` — multi-turn conversational agent (Part 5).
* :mod:`app.services.classifier` — support-ticket classification (Part 6).
* :mod:`app.services.summariser` — book-review summarisation (Part 6).

Each service is constructed via the dependency container (defined later)
to keep them testable and free of global state.
"""

# Product Requirements Document — LibraryMind

| | |
|---|---|
| **Document owner** | Gisa Mugisha Caleb Pacifique |
| **Status** | Draft — Phase 0 |
| **Last updated** | 2026-05-15 |
| **Source of truth for grading** | `Module_10_Lab_write_up.pdf` |

---

## 1. Project Overview

LibraryMind is an AI-powered backend service for a public library. It augments a traditional catalogue with capabilities that exact-keyword search cannot deliver: understanding a question's *meaning*, holding a multi-turn conversation, summarising large bodies of opinion, and triaging unstructured support requests.

The deliverable is a self-contained FastAPI application that exposes six REST endpoints, backed by a vector database (ChromaDB), an optional Redis cache, and a multi-provider AI layer that survives any single vendor going down.

The project is the capstone of an AI engineering module. It consolidates the techniques taught throughout the module — provider abstraction, vector search, retrieval-augmented generation, structured-output prompting, conversational memory, caching, rate limiting, and cost observability — into a single shippable artefact.

## 2. Goals

The primary goal is to demonstrate that an AI feature can be productionised: it must remain available when a provider fails, predictable when traffic spikes, and observable enough that cost is never a surprise. Secondarily, the system must serve as a reference architecture the engineer can extend: a new provider, a new collection, or a new endpoint should each be additions of a single module rather than rewrites.

Concretely, by the end of Phase 8 the system must satisfy every acceptance criterion listed in Parts 0–8 of the lab brief, and the codebase must read cleanly enough to score full marks under the "code quality, structure, and README" rubric line.

## 3. Non-Goals

The lab does not require user accounts, multi-tenancy, role-based access control, payment, or any client-facing UI. The catalogue is a static seed dataset of ≥20 books; cataloguing workflows (acquisition, cataloguing, weeding) are out of scope. A frontend is reserved for a future phase but is not part of grading.

Persistence is deliberately minimal: the lab brief permits in-memory storage for conversations, support tickets, and usage records. We will not introduce PostgreSQL, SQLAlchemy, Alembic, or Celery in this lab — adding them would inflate complexity without earning any rubric points and would violate the "do not over-engineer" constraint.

## 4. Target Users

The application has two effective user classes. *Patrons* interact with the system through the REST API (and in a future phase, through a web client). They expect natural-language queries to return relevant, cited answers and for the assistant to remember the previous turn of the conversation. *Operators* — the engineers running the service — interact through the `/health` endpoint, structured logs, and the seeding script; they expect every external call to be costed, every cache hit to be visible, and every failure to be diagnosable.

## 5. Assumptions

We assume the operator has API credentials for at least one of OpenAI, Anthropic, or AmaliAI. We assume the seed catalogue (`app/data/books.json`) is curated by the operator and seeded explicitly via a script — there is no admin endpoint for ingest in this lab. We assume Redis is available locally for caching, but the system must remain functional without it. We assume traffic volume is low (≤60 RPM by default), so the in-memory rate limiter and usage tracker are sufficient and do not need to be distributed.

## 6. Constraints

The implementation language is Python 3.11+. The web framework must be FastAPI. The vector database must support cosine similarity and persist locally without a server process — ChromaDB satisfies this. The application must start successfully with as few as one provider configured. Each AI call must be retried with exponential backoff before falling through to the next provider. Every external call must be tokenised and costed in USD against a per-model price table.

The internal collaboration files (`Agent.md`, `Guidelines.md`, `handoff.md`) are deliberately git-ignored: they support AI-assisted development but are not part of the public repository.

## 7. Functional Requirements

The system exposes six HTTP endpoints. `POST /search/books` performs semantic search over the catalogue and returns up to N books ranked by cosine similarity. `POST /search/ask` performs retrieval-augmented Q&A: it embeds the question, retrieves relevant catalogue records, applies a relevance threshold, and prompts the AI to answer using only the retrieved context. The response includes both the answer text and the source books cited. `POST /chat` accepts a `conversation_id` and a user message, retrieves RAG context, includes truncated conversation history, and returns the assistant's reply. `POST /classify/ticket` returns structured JSON containing the ticket's category, priority, sentiment, suggested department, and a one-sentence summary. `POST /summarise/reviews` accepts 1–50 reviews and returns themes, praise, criticism, an estimated 1–5 rating, and a recommendation. `GET /health` reports application status, daily spend, and request count.

All endpoints accept and return JSON. All input is validated by Pydantic models with explicit minimum and maximum lengths. All AI responses are passed through a JSON-recovery helper that strips markdown code fences before parsing.

## 8. Non-Functional Requirements

The application must respond to a cache-hit query in under 100 ms locally. A cache-miss query depends primarily on the upstream provider's latency; we target sub-three-second end-to-end response for a typical RAG question. The system must survive primary-provider failure without restart: removing the primary key and retrying must produce a successful response from the fallback provider, with the retry attempt visible in logs. The token-bucket rate limiter must reject the 61st request in a 60-second window when configured at 60 RPM. The usage tracker must report a non-zero daily cost after any non-cached AI call.

Logs must be structured JSON in production and human-readable in development. Every log line associated with a request must carry the same request ID. Every AI call must log provider, model, prompt token count, completion token count, and estimated cost.

## 9. System Behaviours

When a patron asks a question, the RAG engine first consults the cache; on a hit the cached answer is returned with `cached=true`. On a miss the rate limiter is consulted; rejection produces an HTTP 429 with a clear message. The question is embedded (with embedding cache lookup), the top-K candidates are retrieved from ChromaDB, low-relevance results are dropped, and if nothing remains the assistant returns a polite refusal rather than fabricating an answer. The remaining context is formatted into a structured block, combined with the system prompt, and dispatched through the resilient provider orchestrator. On success, usage is recorded, the response is cached for future identical queries, and the JSON envelope is returned. On failure of every provider, an HTTP 503 with a descriptive message is returned.

The chatbot follows the same flow but additionally retrieves the conversation's prior messages, truncates them to the most recent N (configurable), and prepends them to the prompt. Conversations are isolated by ID; messages never bleed between conversation IDs.

## 10. Future Considerations

A future iteration would persist conversations, support tickets, and usage records to a real database for analytics. Distributed deployments would replace the in-process rate limiter and in-memory usage tracker with Redis-backed equivalents. Asynchronous workflows — pre-warming embeddings for newly ingested books, periodically rolling up usage records — would move to Celery or an equivalent task queue. A frontend would consume the REST API as designed. None of these are part of the current lab scope, but the architecture leaves room for each: services are defined behind interfaces, schemas are version-friendly, and infrastructure components are encapsulated.
